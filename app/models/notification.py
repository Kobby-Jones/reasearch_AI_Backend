from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    """An in-app notification for a user (report ready, payment, milestones)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), default="info")  # info|success|warning
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class SharedReport(Base, TimestampMixin):
    """A read-only, public HTML snapshot of a generated report, by token."""

    __tablename__ = "shared_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    html: Mapped[str] = mapped_column(Text)  # pre-rendered, self-contained body
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
