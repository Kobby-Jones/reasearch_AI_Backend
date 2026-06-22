from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        user_id: int,
        action: str,
        *,
        target_type: str | None = None,
        target_id: int | None = None,
        summary: str | None = None,
        meta: dict | None = None,
        commit: bool = True,
    ) -> AuditEvent:
        """Append an audit event. Best-effort: never raises into the caller."""
        try:
            event = AuditEvent(
                user_id=user_id, action=action, target_type=target_type,
                target_id=target_id, summary=summary, meta=meta,
            )
            self.db.add(event)
            if commit:
                self.db.commit()
            return event
        except Exception:
            self.db.rollback()
            return None  # type: ignore[return-value]

    def list_for_user(self, user_id: int, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        return list(
            self.db.scalars(
                select(AuditEvent)
                .where(AuditEvent.user_id == user_id)
                .order_by(AuditEvent.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )


def audit(db: Session, user_id: int, action: str, **kwargs) -> None:
    """Convenience one-liner used by routers."""
    AuditService(db).record(user_id, action, **kwargs)
