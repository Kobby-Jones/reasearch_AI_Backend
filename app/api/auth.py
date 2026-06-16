from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserOut:
    user = AuthService(db).register(payload.email, payload.password, payload.full_name)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService(db).login(payload.email, payload.password)
    return TokenResponse(access_token=token)


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
