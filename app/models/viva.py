from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.research import ResearchProject


class VivaSession(Base, TimestampMixin):
    __tablename__ = "viva_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    examiner_role: Mapped[str] = mapped_column(String(64), default="supervisor")
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|completed
    transcript: Mapped[list] = mapped_column(JSON, default=list)        # [{q,a,score,...}]
    readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weak_areas: Mapped[list | None] = mapped_column(JSON, nullable=True)

    project: Mapped["ResearchProject"] = relationship(back_populates="viva_sessions")
