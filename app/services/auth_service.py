from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, ValidationError
from app.core.security import (
    create_access_token,
    create_signed_token,
    decode_signed_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.models.user import User
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.models.subscription import Subscription
from app.services.email_service import email_service


def _verify_link(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/verify-email?token={token}"


def _reset_link(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def _send_verification(self, user: User) -> None:
        token = create_signed_token(user.id, "verify_email", settings.verify_token_minutes)
        email_service.send_verification(user.email, _verify_link(token))

    def register(self, email: str, password: str, full_name: str | None,
                 referral_code: str | None = None) -> User:
        email = email.strip().lower()
        if self.users.get_by_email(email):
            raise ValidationError("An account with that email already exists.")
        referred_by_id = None
        if referral_code:
            from app.services.growth_service import GrowthService
            referred_by_id = GrowthService(self.db).resolve_referrer(referral_code)
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            referred_by_id=referred_by_id,
        )
        self.users.add(user)
        # every new user starts on a free subscription
        SubscriptionRepository(self.db).add(
            Subscription(user_id=user.id, plan="free", status="active")
        )
        try:
            self.db.commit()
        except IntegrityError:
            # Two concurrent registrations for the same email can both pass the
            # pre-check; the unique constraint is the source of truth.
            self.db.rollback()
            raise ValidationError("An account with that email already exists.")
        self._send_verification(user)  # best-effort
        return user

    # ---- email verification --------------------------------------------------
    def verify_email(self, token: str) -> bool:
        sub = decode_signed_token(token, "verify_email")
        if not sub:
            raise ValidationError("This verification link is invalid or has expired.")
        user = self.users.get(int(sub))
        if not user:
            raise ValidationError("Account not found.")
        if not user.email_verified:
            user.email_verified = True
            self.db.commit()
        return True

    def resend_verification(self, user: User) -> None:
        if user.email_verified:
            return
        self._send_verification(user)

    # ---- password reset ------------------------------------------------------
    def request_password_reset(self, email: str) -> None:
        """Always succeeds from the caller's view (no account enumeration)."""
        user = self.users.get_by_email(email.strip().lower())
        if user:
            token = create_signed_token(user.id, "reset_password", settings.reset_token_minutes)
            email_service.send_password_reset(user.email, _reset_link(token))

    def reset_password(self, token: str, new_password: str) -> None:
        sub = decode_signed_token(token, "reset_password")
        if not sub:
            raise ValidationError("This reset link is invalid or has expired.")
        if len(new_password) < 8:
            raise ValidationError("Password must be at least 8 characters.")
        user = self.users.get(int(sub))
        if not user:
            raise ValidationError("Account not found.")
        user.password_hash = hash_password(new_password)
        self.db.commit()

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email(email.strip().lower())
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        if not user.is_active:
            raise AuthError("Account is disabled.")
        return create_access_token(user.id)

    def complete_onboarding(self, user: User) -> User:
        if not user.onboarding_completed:
            user.onboarding_completed = True
            self.db.commit()
            self.db.refresh(user)
        return user
