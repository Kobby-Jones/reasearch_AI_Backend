from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limit_ip
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

_auth_rl = limit_ip("auth", settings.rate_limit_auth_per_min, 60)


class TokenBody(BaseModel):
    token: str


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class SimpleMessage(BaseModel):
    ok: bool = True
    message: str


@router.post("/register", response_model=UserOut, status_code=201, dependencies=[Depends(_auth_rl)])
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    user = AuthService(db).register(payload.email, payload.password, payload.full_name, payload.referral_code)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_auth_rl)])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService(db).login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.post("/verify-email", response_model=SimpleMessage)
def verify_email(payload: TokenBody, db: Session = Depends(get_db)) -> SimpleMessage:
    AuthService(db).verify_email(payload.token)
    return SimpleMessage(message="Your email has been verified.")


@router.post("/resend-verification", response_model=SimpleMessage)
def resend_verification(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> SimpleMessage:
    AuthService(db).resend_verification(user)
    return SimpleMessage(message="If your email is unverified, a new link is on its way.")


@router.post("/forgot-password", response_model=SimpleMessage, dependencies=[Depends(_auth_rl)])
def forgot_password(payload: ForgotBody, db: Session = Depends(get_db)) -> SimpleMessage:
    AuthService(db).request_password_reset(payload.email)
    # Always the same response, regardless of whether the account exists.
    return SimpleMessage(message="If an account exists for that email, a reset link has been sent.")


@router.post("/reset-password", response_model=SimpleMessage, dependencies=[Depends(_auth_rl)])
def reset_password(payload: ResetBody, db: Session = Depends(get_db)) -> SimpleMessage:
    AuthService(db).reset_password(payload.token, payload.new_password)
    return SimpleMessage(message="Your password has been reset. You can now sign in.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/me/onboarding", response_model=UserOut)
def complete_onboarding(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    updated = AuthService(db).complete_onboarding(user)
    return UserOut.model_validate(updated)
