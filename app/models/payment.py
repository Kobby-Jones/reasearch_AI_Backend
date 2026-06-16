from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)            # minor units
    currency: Mapped[str] = mapped_column(String(8), default="GHS")
    provider: Mapped[str] = mapped_column(String(32), default="paystack")
    plan: Mapped[str] = mapped_column(String(16))           # target plan
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|success|failed
    channel: Mapped[str | None] = mapped_column(String(16), nullable=True)   # mobile_money|card
    interval: Mapped[str | None] = mapped_column(String(16), nullable=True)  # monthly|annual

    user: Mapped["User"] = relationship(back_populates="payments")
