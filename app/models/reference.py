from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.research import ResearchProject


class ProjectReference(Base, TimestampMixin):
    """A curated scholarly reference saved to a project's citation library.

    Mirrors the fields of app.ai.references.Reference so a row can be turned
    back into that dataclass to reuse APA / in-text formatting, and so the
    report writer can cite from the same curated set the user manages here.
    """

    __tablename__ = "project_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    citation_key: Mapped[str] = mapped_column(String(64))
    authors: Mapped[list] = mapped_column(JSON, default=list)  # ["Surname, I.", ...]
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    container: Mapped[str | None] = mapped_column(Text, nullable=True)
    volume: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issue: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(64), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_by: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # openalex|crossref|doi|bibtex|manual

    project: Mapped["ResearchProject"] = relationship()
