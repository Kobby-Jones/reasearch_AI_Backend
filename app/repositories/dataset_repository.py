from __future__ import annotations

from sqlalchemy import select

from app.models.dataset import Dataset
from app.repositories.base import BaseRepository


class DatasetRepository(BaseRepository[Dataset]):
    model = Dataset

    def list_for_project(
        self, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[Dataset]:
        return list(
            self.db.scalars(
                select(Dataset)
                .where(Dataset.project_id == project_id)
                .order_by(Dataset.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
