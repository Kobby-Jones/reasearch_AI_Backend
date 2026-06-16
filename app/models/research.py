from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.questionnaire import Questionnaire
    from app.models.dataset import Dataset
    from app.models.viva import VivaSession


class ResearchProject(Base, TimestampMixin):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(512))
    field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Structured breakdown produced by the research service.
    variables: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    objectives: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hypotheses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    methodology: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="projects")
    questionnaires: Mapped[list["Questionnaire"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    viva_sessions: Mapped[list["VivaSession"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
