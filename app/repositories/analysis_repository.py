from __future__ import annotations

from sqlalchemy import select

from app.models.analysis import AnalysisResult
from app.models.dataset import Dataset
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[AnalysisResult]):
    model = AnalysisResult

    def list_for_dataset(
        self, dataset_id: int, limit: int = 100, offset: int = 0
    ) -> list[AnalysisResult]:
        return list(
            self.db.scalars(
                select(AnalysisResult)
                .where(AnalysisResult.dataset_id == dataset_id)
                .order_by(AnalysisResult.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def list_for_project(
        self, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[AnalysisResult]:
        # Analyses belong to datasets, which belong to projects — join through.
        return list(
            self.db.scalars(
                select(AnalysisResult)
                .join(Dataset, AnalysisResult.dataset_id == Dataset.id)
                .where(Dataset.project_id == project_id)
                .order_by(AnalysisResult.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
