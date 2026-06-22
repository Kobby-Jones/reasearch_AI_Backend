from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditEventOut(BaseModel):
    id: int
    action: str
    target_type: str | None = None
    target_id: int | None = None
    summary: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=list[AuditEventOut])
def list_events(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditEventOut]:
    return [AuditEventOut.model_validate(e) for e in AuditService(db).list_for_user(user.id, limit, offset)]
