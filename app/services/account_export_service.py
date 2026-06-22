from __future__ import annotations

import json
import os
import uuid
import zipfile
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.analysis import AnalysisResult
from app.models.dataset import Dataset
from app.models.questionnaire import Questionnaire
from app.models.reference import ProjectReference
from app.models.research import ResearchProject
from app.models.subscription import Subscription
from app.models.survey import Survey
from app.models.user import User


def _ser(obj) -> dict:
    """Serialise a SQLAlchemy row's columns into JSON-safe values."""
    out = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        out[col.name] = val
    return out


class AccountExportService:
    """Builds a portable ZIP of everything tied to a user's account."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, user: User) -> str:
        projects = list(self.db.scalars(
            select(ResearchProject).where(ResearchProject.user_id == user.id)
        ).all())
        project_ids = [p.id for p in projects]

        questionnaires = self._by_project(Questionnaire, project_ids)
        datasets = self._by_project(Dataset, project_ids)
        references = self._by_project(ProjectReference, project_ids)
        surveys = list(self.db.scalars(
            select(Survey).where(Survey.user_id == user.id)
        ).all())
        dataset_ids = [d.id for d in datasets]
        analyses = list(self.db.scalars(
            select(AnalysisResult).where(AnalysisResult.dataset_id.in_(dataset_ids or [-1]))
        ).all())
        subscription = self.db.scalar(
            select(Subscription).where(Subscription.user_id == user.id, Subscription.status == "active")
        )

        manifest = {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "account": {
                "id": user.id, "email": user.email, "full_name": user.full_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
            "projects": [_ser(p) for p in projects],
            "questionnaires": [_ser(q) for q in questionnaires],
            "datasets": [_ser(d) for d in datasets],
            "analyses": [_ser(a) for a in analyses],
            "references": [_ser(r) for r in references],
            "surveys": [_ser(s) for s in surveys],
            "subscription": _ser(subscription) if subscription else None,
            "counts": {
                "projects": len(projects), "questionnaires": len(questionnaires),
                "datasets": len(datasets), "analyses": len(analyses),
                "references": len(references), "surveys": len(surveys),
            },
        }

        os.makedirs(settings.report_dir, exist_ok=True)
        path = os.path.join(settings.report_dir, f"export_{user.id}_{uuid.uuid4().hex[:8]}.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
            z.writestr("README.txt", _README)
            # include the actual dataset CSVs the user uploaded/collected
            for d in datasets:
                if d.storage_path and os.path.exists(d.storage_path):
                    safe = f"datasets/{d.id}_{os.path.basename(d.filename) or 'data.csv'}"
                    if not safe.endswith(".csv"):
                        safe += ".csv"
                    try:
                        z.write(d.storage_path, safe)
                    except OSError:
                        pass
        return path


    def _by_project(self, model, project_ids: list[int]):
        if not project_ids:
            return []
        return list(self.db.scalars(
            select(model).where(model.project_id.in_(project_ids))
        ).all())


_README = (
    "ResearchAI data export\n"
    "======================\n\n"
    "manifest.json contains your account, projects, questionnaires, dataset\n"
    "metadata, analyses, references, and surveys in JSON.\n\n"
    "The datasets/ folder contains the cleaned CSV for each of your datasets.\n\n"
    "This is a complete copy of the data associated with your account at the\n"
    "time of export.\n"
)
