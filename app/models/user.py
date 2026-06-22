from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.research import ResearchProject
    from app.models.subscription import Subscription
    from app.models.payment import Payment
    from app.models.usage import UsageRecord


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    student_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True, index=True)
    referred_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list["ResearchProject"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
