from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.research import ResearchProject
    from app.models.analysis import AnalysisResult


class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    storage_path: Mapped[str] = mapped_column(String(1024))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    schema_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cleaning_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped["ResearchProject"] = relationship(back_populates="datasets")
    analyses: Mapped[list["AnalysisResult"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
