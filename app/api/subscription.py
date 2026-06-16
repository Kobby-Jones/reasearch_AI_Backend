from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.subscription import SubscriptionStatus
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/status", response_model=SubscriptionStatus)
def status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionStatus:
    return SubscriptionStatus(**SubscriptionService(db).status(user.id))


@router.post("/cancel", response_model=SubscriptionStatus)
def cancel(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionStatus:
    return SubscriptionStatus(**SubscriptionService(db).cancel(user.id))


@router.post("/resume", response_model=SubscriptionStatus)
def resume(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionStatus:
    return SubscriptionStatus(**SubscriptionService(db).resume(user.id))
