from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UsageRecord(Base, TimestampMixin):
    """Per-user, per-period usage counters for scaling + pricing analytics."""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)  # ai_calls|analysis_runs|...
    period: Mapped[str] = mapped_column(String(8), index=True)   # YYYY-MM
    count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="usage_records")
