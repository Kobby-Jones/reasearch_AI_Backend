from __future__ import annotations

import csv
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import get_ai_client
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.models.analysis import AnalysisResult
from app.models.dataset import Dataset
from app.models.questionnaire import Questionnaire
from app.models.research import ResearchProject
from app.repositories.research_repository import ResearchRepository
from app.services import sample_data as sd
from app.utils.usage_tracker import UsageTracker, AI_CALLS


class ResearchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ResearchRepository(db)
        self.ai = get_ai_client()
        self.tracker = UsageTracker(db)

    def create_from_topic(self, user_id: int, topic: str, field: str | None) -> ResearchProject:
        breakdown = self.ai.break_down_topic(topic, field)
        self.tracker.increment(user_id, AI_CALLS)

        project = ResearchProject(
            user_id=user_id,
            topic=topic,
            field=field,
            variables=breakdown.get("variables"),
            objectives=breakdown.get("objectives"),
            hypotheses=breakdown.get("hypotheses"),
            methodology=breakdown.get("methodology"),
        )
        self.repo.add(project)
        self.db.commit()
        return project

    def get_owned(self, project_id: int, user_id: int) -> ResearchProject:
        project = self.repo.get_owned(project_id, user_id)
        if not project:
            raise NotFoundError("Research project not found.")
        return project

    def list_for_user(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[ResearchProject]:
        return self.repo.list_for_user(user_id, limit=limit, offset=offset)

    def existing_sample(self, user_id: int) -> ResearchProject | None:
        return self.db.scalar(
            select(ResearchProject).where(
                ResearchProject.user_id == user_id,
                ResearchProject.is_sample.is_(True),
            )
        )

    def create_sample(self, user_id: int) -> ResearchProject:
        """Seed a complete, explorable demo project. Idempotent per user.

        Creates the topic breakdown, a validated questionnaire, a real sample
        dataset (written to storage), and two analyses with interpretations.
        Uses no AI or analysis quota.
        """
        existing = self.existing_sample(user_id)
        if existing:
            return existing

        project = ResearchProject(
            user_id=user_id,
            topic=sd.SAMPLE_TOPIC,
            field=sd.SAMPLE_FIELD,
            variables=sd.SAMPLE_VARIABLES,
            objectives=sd.SAMPLE_OBJECTIVES,
            hypotheses=sd.SAMPLE_HYPOTHESES,
            methodology=sd.SAMPLE_METHODOLOGY,
            summary=sd.SAMPLE_SUMMARY,
            is_sample=True,
        )
        self.repo.add(project)
        self.db.flush()  # assign project.id

        # Questionnaire
        self.db.add(
            Questionnaire(
                project_id=project.id,
                title=sd.SAMPLE_QUESTIONNAIRE_TITLE,
                structure=sd.SAMPLE_QUESTIONNAIRE,
                clarity_score=sd.SAMPLE_QUESTIONNAIRE_CLARITY,
                validation=sd.SAMPLE_QUESTIONNAIRE_VALIDATION,
            )
        )

        # Dataset: write a real CSV to the configured upload directory.
        storage_path = self._write_sample_csv(user_id, project.id)
        dataset = Dataset(
            project_id=project.id,
            filename=sd.SAMPLE_DATASET_FILENAME,
            storage_path=storage_path,
            row_count=len(sd.SAMPLE_DATASET_ROWS),
            column_count=len(sd.SAMPLE_DATASET_COLUMNS),
            schema_info=sd.SAMPLE_DATASET_SCHEMA,
            cleaning_report=sd.SAMPLE_DATASET_CLEANING,
        )
        self.db.add(dataset)
        self.db.flush()  # assign dataset.id

        # Analyses (canned, consistent with the dataset)
        self.db.add(
            AnalysisResult(
                dataset_id=dataset.id,
                analysis_type="descriptive",
                parameters={"columns": sd.SAMPLE_DATASET_COLUMNS},
                results=sd.SAMPLE_DESCRIPTIVE_RESULTS,
                interpretation=sd.SAMPLE_DESCRIPTIVE_INTERPRETATION,
            )
        )
        self.db.add(
            AnalysisResult(
                dataset_id=dataset.id,
                analysis_type="correlation",
                parameters={"method": "pearson", "columns": sd.SAMPLE_DATASET_COLUMNS},
                results=sd.SAMPLE_CORRELATION_RESULTS,
                interpretation=sd.SAMPLE_CORRELATION_INTERPRETATION,
            )
        )

        self.db.commit()
        self.db.refresh(project)
        return project

    def _write_sample_csv(self, user_id: int, project_id: int) -> str:
        directory = Path(settings.upload_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"sample_u{user_id}_p{project_id}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(sd.SAMPLE_DATASET_COLUMNS)
            writer.writerows(sd.SAMPLE_DATASET_ROWS)
        return str(path)
