from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.research import ResearchProject
    from app.models.questionnaire import Questionnaire


class Survey(Base, TimestampMixin):
    """A questionnaire published as a public, shareable web survey."""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    questionnaire_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="CASCADE"), index=True
    )
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|closed
    # Snapshot of the instrument at publish time, so later edits to the source
    # questionnaire never change a live survey out from under its respondents.
    structure: Mapped[dict] = mapped_column(JSON)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    responses: Mapped[list["SurveyResponse"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan"
    )


class SurveyResponse(Base, TimestampMixin):
    """A single submitted response to a survey (created_at == submitted at)."""

    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), index=True
    )
    answers: Mapped[dict] = mapped_column(JSON)  # {item_id: value}
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    survey: Mapped["Survey"] = relationship(back_populates="responses")
