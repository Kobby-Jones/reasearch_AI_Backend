from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class AuditEvent(Base, TimestampMixin):
    """An append-only record of a meaningful action a user took.

    Gives users (and support) a verifiable history of what happened to their
    data: projects created, datasets uploaded/anonymised, analyses run, reports
    exported, data exported, and so on.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)   # e.g. "dataset.upload"
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # project|dataset|...
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
