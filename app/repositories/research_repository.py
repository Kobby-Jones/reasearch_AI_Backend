from __future__ import annotations

from sqlalchemy import select

from app.models.research import ResearchProject
from app.repositories.base import BaseRepository


class ResearchRepository(BaseRepository[ResearchProject]):
    model = ResearchProject

    def list_for_user(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[ResearchProject]:
        return list(
            self.db.scalars(
                select(ResearchProject)
                .where(ResearchProject.user_id == user_id)
                .order_by(ResearchProject.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def get_owned(self, project_id: int, user_id: int) -> ResearchProject | None:
        return self.db.scalar(
            select(ResearchProject).where(
                ResearchProject.id == project_id,
                ResearchProject.user_id == user_id,
            )
        )
