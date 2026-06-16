from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.dataset import Dataset


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(64))   # descriptive|correlation|...
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    results: Mapped[dict] = mapped_column(JSON)              # deterministic engine output
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped["Dataset"] = relationship(back_populates="analyses")
