from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def push(self, user_id: int, title: str, *, body: str | None = None,
             type: str = "info", link: str | None = None, commit: bool = True) -> Notification | None:
        """Create a notification. Best-effort; never raises into the caller."""
        try:
            n = Notification(user_id=user_id, title=title, body=body, type=type, link=link)
            self.db.add(n)
            if commit:
                self.db.commit()
            return n
        except Exception:
            self.db.rollback()
            return None

    def list(self, user_id: int, limit: int = 30) -> list[Notification]:
        return list(self.db.scalars(
            select(Notification).where(Notification.user_id == user_id)
            .order_by(Notification.id.desc()).limit(limit)
        ).all())

    def unread_count(self, user_id: int) -> int:
        return int(self.db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.read.is_(False))
        ) or 0)

    def mark_read(self, user_id: int, notification_id: int) -> None:
        self.db.execute(
            update(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            ).values(read=True)
        )
        self.db.commit()

    def mark_all_read(self, user_id: int) -> None:
        self.db.execute(
            update(Notification).where(
                Notification.user_id == user_id, Notification.read.is_(False)
            ).values(read=True)
        )
        self.db.commit()


def notify(db: Session, user_id: int, title: str, **kwargs) -> None:
    NotificationService(db).push(user_id, title, **kwargs)
