from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.research import ResearchProject


class Questionnaire(Base, TimestampMixin):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(nullable=True)
    structure: Mapped[dict] = mapped_column(JSON)          # sections + items
    clarity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped["ResearchProject"] = relationship(back_populates="questionnaires")
