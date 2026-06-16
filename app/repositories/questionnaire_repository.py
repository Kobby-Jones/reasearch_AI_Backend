from __future__ import annotations

from sqlalchemy import select

from app.models.questionnaire import Questionnaire
from app.repositories.base import BaseRepository


class QuestionnaireRepository(BaseRepository[Questionnaire]):
    model = Questionnaire

    def list_for_project(
        self, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[Questionnaire]:
        return list(
            self.db.scalars(
                select(Questionnaire)
                .where(Questionnaire.project_id == project_id)
                .order_by(Questionnaire.id.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
