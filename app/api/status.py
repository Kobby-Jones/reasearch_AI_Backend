from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(prefix="/status", tags=["status"])


class Component(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class StatusOut(BaseModel):
    status: str            # operational | degraded
    time: datetime
    components: list[Component]


@router.get("", response_model=StatusOut)
def status(db: Session = Depends(get_db)) -> StatusOut:
    """Public health check powering the status page and the footer pill."""
    components: list[Component] = [Component(name="API", ok=True)]

    # Database connectivity
    try:
        db.execute(text("SELECT 1"))
        components.append(Component(name="Database", ok=True))
    except Exception:
        components.append(Component(name="Database", ok=False, detail="unreachable"))

    # Feature switches (informational, always "ok" when enabled)
    components.append(Component(
        name="Scholarly references",
        ok=bool(getattr(settings, "references_enabled", True)),
        detail=None if getattr(settings, "references_enabled", True) else "disabled",
    ))

    overall = "operational" if all(c.ok for c in components) else "degraded"
    return StatusOut(status=overall, time=datetime.utcnow(), components=components)
