from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notification", tags=["notification"])


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str | None = None
    link: str | None = None
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


@router.get("", response_model=NotificationList)
def list_notifications(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationList:
    svc = NotificationService(db)
    return NotificationList(
        items=[NotificationOut.model_validate(n) for n in svc.list(user.id, limit)],
        unread=svc.unread_count(user.id),
    )


@router.post("/{notification_id}/read", status_code=204, response_class=Response)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    NotificationService(db).mark_read(user.id, notification_id)
    return Response(status_code=204)


@router.post("/read-all", status_code=204, response_class=Response)
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    NotificationService(db).mark_all_read(user.id)
    return Response(status_code=204)
