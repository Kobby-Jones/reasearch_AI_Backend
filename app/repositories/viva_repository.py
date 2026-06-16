from __future__ import annotations

from sqlalchemy import select

from app.models.viva import VivaSession
from app.repositories.base import BaseRepository


class VivaRepository(BaseRepository[VivaSession]):
    model = VivaSession

    def list_for_project(
        self, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[VivaSession]:
        return list(
            self.db.scalars(
                select(VivaSession)
                .where(VivaSession.project_id == project_id)
                .order_by(VivaSession.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
