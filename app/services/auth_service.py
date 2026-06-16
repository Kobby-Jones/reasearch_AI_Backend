from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AuthError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.models.subscription import Subscription


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register(self, email: str, password: str, full_name: str | None) -> User:
        email = email.strip().lower()
        if self.users.get_by_email(email):
            raise ValidationError("An account with that email already exists.")
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
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
        return user

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
