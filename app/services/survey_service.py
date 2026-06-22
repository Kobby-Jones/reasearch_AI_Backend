from __future__ import annotations

import csv
import os
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dataset import Dataset
from app.models.questionnaire import Questionnaire
from app.models.survey import Survey, SurveyResponse
from app.repositories.dataset_repository import DatasetRepository
from app.services.research_service import ResearchService


def _ordered_columns(structure: dict) -> list[tuple[str, str]]:
    """Flatten a questionnaire structure into ordered (column_id, label) pairs."""
    cols: list[tuple[str, str]] = []
    for s_idx, section in enumerate(structure.get("sections") or []):
        items = section.get("items") or []
        for i_idx, item in enumerate(items):
            if isinstance(item, dict):
                cid = str(item.get("id") or f"s{s_idx + 1}_{i_idx + 1}")
                label = str(item.get("text") or cid)
            else:
                cid = f"s{s_idx + 1}_{i_idx + 1}"
                label = str(item)
            cols.append((cid, label))
    return cols


class SurveyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.research = ResearchService(db)

    # ---- ownership helpers ---------------------------------------------------
    def _questionnaire_owned(self, questionnaire_id: int, user_id: int) -> Questionnaire:
        q = self.db.get(Questionnaire, questionnaire_id)
        if not q:
            raise NotFoundError("Questionnaire not found.")
        # resolving the project for this user enforces ownership
        self.research.get_owned(q.project_id, user_id)
        return q

    def get_owned(self, survey_id: int, user_id: int) -> Survey:
        survey = self.db.get(Survey, survey_id)
        if not survey or survey.user_id != user_id:
            raise NotFoundError("Survey not found.")
        return survey

    # ---- owner operations ----------------------------------------------------
    def create(self, user_id: int, questionnaire_id: int, title: str | None) -> Survey:
        q = self._questionnaire_owned(questionnaire_id, user_id)
        if not (q.structure and (q.structure.get("sections"))):
            raise ValidationError("This questionnaire has no items to publish yet.")
        survey = Survey(
            user_id=user_id,
            project_id=q.project_id,
            questionnaire_id=q.id,
            public_token=secrets.token_urlsafe(12),
            title=title or q.title or "Research Survey",
            status="open",
            structure=q.structure,  # snapshot
        )
        self.db.add(survey)
        self.db.commit()
        self.db.refresh(survey)
        return survey

    def list_for_project(self, user_id: int, project_id: int) -> list[Survey]:
        self.research.get_owned(project_id, user_id)
        return list(
            self.db.scalars(
                select(Survey)
                .where(Survey.user_id == user_id, Survey.project_id == project_id)
                .order_by(Survey.id.desc())
            ).all()
        )

    def set_status(self, user_id: int, survey_id: int, status: str) -> Survey:
        survey = self.get_owned(survey_id, user_id)
        survey.status = status
        survey.closed_at = datetime.now(timezone.utc) if status == "closed" else None
        self.db.commit()
        self.db.refresh(survey)
        return survey

    def count_responses(self, survey_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(SurveyResponse.id)).where(SurveyResponse.survey_id == survey_id)
            )
            or 0
        )

    def list_responses(self, user_id: int, survey_id: int) -> list[SurveyResponse]:
        self.get_owned(survey_id, user_id)
        return list(
            self.db.scalars(
                select(SurveyResponse)
                .where(SurveyResponse.survey_id == survey_id)
                .order_by(SurveyResponse.id.asc())
            ).all()
        )

    def analytics(self, user_id: int, survey_id: int) -> dict:
        """Per-question response summaries for the results dashboard."""
        from app.services.survey_analytics import build_analytics

        survey = self.get_owned(survey_id, user_id)
        responses = [r.answers or {} for r in self.list_responses(user_id, survey_id)]
        out = build_analytics(self.effective_structure(survey), responses)
        out["survey_id"] = survey.id
        out["title"] = survey.title
        return out

    def serialize(self, survey: Survey) -> dict:
        return {
            "id": survey.id,
            "project_id": survey.project_id,
            "questionnaire_id": survey.questionnaire_id,
            "public_token": survey.public_token,
            "title": survey.title,
            "status": survey.status,
            "created_at": survey.created_at,
            "closed_at": survey.closed_at,
            "response_count": self.count_responses(survey.id),
            "public_url": f"{settings.frontend_url.rstrip('/')}/s/{survey.public_token}",
        }

    # ---- public (unauthenticated) operations ---------------------------------
    def public_get(self, token: str) -> Survey:
        survey = self.db.scalar(select(Survey).where(Survey.public_token == token))
        if not survey:
            raise NotFoundError("Survey not found.")
        return survey

    def effective_structure(self, survey: Survey) -> dict:
        """The structure to serve for a survey: the linked questionnaire's CURRENT
        structure when it still exists (so edits propagate to the shared link),
        falling back to the snapshot taken at publish time."""
        from app.models.questionnaire import Questionnaire

        q = self.db.get(Questionnaire, survey.questionnaire_id)
        if q and q.structure and q.structure.get("sections"):
            return q.structure
        return survey.structure

    def submit_response(self, token: str, answers: dict, meta: dict | None) -> SurveyResponse:
        survey = self.public_get(token)
        if survey.status != "open":
            raise ValidationError("This survey is closed and is no longer accepting responses.")
        if not isinstance(answers, dict) or not answers:
            raise ValidationError("No answers were submitted.")
        # keep only known columns to avoid storing arbitrary payloads
        valid_ids = {cid for cid, _ in _ordered_columns(self.effective_structure(survey))}
        cleaned = {k: v for k, v in answers.items() if k in valid_ids}
        if not cleaned:
            raise ValidationError("Submitted answers did not match this survey.")
        resp = SurveyResponse(survey_id=survey.id, answers=cleaned, meta=meta)
        self.db.add(resp)
        self.db.commit()
        self.db.refresh(resp)
        return resp

    # ---- import responses into a dataset -------------------------------------
    def import_to_dataset(self, user_id: int, survey_id: int):
        from app.utils.dataset_loader import clean_dataframe, detect_schema, load_dataframe

        survey = self.get_owned(survey_id, user_id)
        responses = self.list_responses(user_id, survey_id)
        if not responses:
            raise ValidationError("There are no responses to import yet.")

        columns = _ordered_columns(self.effective_structure(survey))
        col_ids = [cid for cid, _ in columns]

        os.makedirs(settings.upload_dir, exist_ok=True)
        raw_path = os.path.join(settings.upload_dir, f"survey_{survey.id}_{uuid.uuid4().hex}.csv")
        with open(raw_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(col_ids)
            for r in responses:
                row = []
                for cid in col_ids:
                    val = r.answers.get(cid, "")
                    if isinstance(val, list):
                        val = "; ".join(str(x) for x in val)
                    row.append(val)
                writer.writerow(row)

        df = load_dataframe(raw_path)
        schema = detect_schema(df)
        cleaned, report = clean_dataframe(df)
        cleaned_path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.csv")
        cleaned.to_csv(cleaned_path, index=False)

        dataset = Dataset(
            project_id=survey.project_id,
            filename=f"{(survey.title or 'survey').strip()[:40]} responses.csv",
            storage_path=cleaned_path,
            row_count=int(cleaned.shape[0]),
            column_count=int(cleaned.shape[1]),
            schema_info=schema,
            cleaning_report=report,
        )
        DatasetRepository(self.db).add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset
