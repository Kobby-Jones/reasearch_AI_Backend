from __future__ import annotations

import io
import os
import uuid

import pandas as pd
from sqlalchemy.orm import Session

from app.connectors import google_sheets, kobo, surveycto
from app.connectors.http import ConnectorError, get_json, get_text
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.dataset import Dataset
from app.repositories.dataset_repository import DatasetRepository
from app.services.research_service import ResearchService
from app.utils.dataset_loader import clean_dataframe, detect_schema


class ConnectorService:
    """Imports external survey data into a project as a cleaned dataset.

    Third-party credentials are used only for the duration of the request and
    are never stored.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.research = ResearchService(db)

    # ---- shared: dataframe -> Dataset ---------------------------------------
    def _dataset_from_dataframe(self, project_id: int, df: pd.DataFrame, filename: str, source: str) -> Dataset:
        if df is None or df.empty:
            raise ValidationError("No rows were returned from the source.")
        # normalise column names to strings
        df.columns = [str(c) for c in df.columns]
        schema = detect_schema(df)
        cleaned, report = clean_dataframe(df)
        report = dict(report or {})
        report["source"] = source
        os.makedirs(settings.upload_dir, exist_ok=True)
        path = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}.csv")
        cleaned.to_csv(path, index=False)
        dataset = Dataset(
            project_id=project_id,
            filename=filename,
            storage_path=path,
            row_count=int(cleaned.shape[0]),
            column_count=int(cleaned.shape[1]),
            schema_info=schema,
            cleaning_report=report,
        )
        DatasetRepository(self.db).add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    # ---- KoboToolbox / ODK ---------------------------------------------------
    def kobo_forms(self, user_id: int, base_url: str, token: str) -> list[dict]:
        return kobo.list_forms(base_url, token, fetch=get_json)

    def kobo_import(self, user_id: int, project_id: int, base_url: str, token: str, form_uid: str, form_name: str | None) -> Dataset:
        self.research.get_owned(project_id, user_id)
        records = kobo.fetch_submissions(base_url, token, form_uid, fetch=get_json)
        df = pd.DataFrame(records)
        name = f"{(form_name or form_uid)}.csv".replace("/", "-")
        return self._dataset_from_dataframe(project_id, df, name, "KoboToolbox")

    # ---- Google Sheets -------------------------------------------------------
    def google_import(self, user_id: int, project_id: int, url: str) -> Dataset:
        self.research.get_owned(project_id, user_id)
        csv_text = google_sheets.fetch_csv(url, fetch=get_text)
        try:
            df = pd.read_csv(io.StringIO(csv_text))
        except Exception as exc:
            raise ConnectorError("The sheet could not be read as a table.") from exc
        return self._dataset_from_dataframe(project_id, df, "Google Sheet.csv", "Google Sheets")

    # ---- SurveyCTO -----------------------------------------------------------
    def surveycto_import(self, user_id: int, project_id: int, server: str, username: str, password: str, form_id: str) -> Dataset:
        self.research.get_owned(project_id, user_id)
        records = surveycto.fetch_submissions(server, username, password, form_id, fetch=get_json)
        df = pd.DataFrame(records)
        return self._dataset_from_dataframe(project_id, df, f"{form_id}.csv", "SurveyCTO")

    # ---- Google Forms (import an instrument, not data) -----------------------
    def google_forms_import(self, user_id: int, project_id: int, url: str):
        """Import an existing public Google Form as a questionnaire."""
        from app.connectors import google_forms
        from app.connectors.http import get_text
        from app.models.questionnaire import Questionnaire
        from app.repositories.questionnaire_repository import QuestionnaireRepository
        from app.services.instrument import sanitize_structure
        from app.services.questionnaire_service import validate_structure

        self.research.get_owned(project_id, user_id)
        structure = google_forms.import_form(url, fetch=get_text)
        title = structure.get("title") or "Imported Google Form"
        clean = sanitize_structure(structure)  # preserve Google's explicit types
        report = validate_structure(clean)
        q = Questionnaire(
            project_id=project_id,
            title=title,
            structure=clean,
            clarity_score=report["clarity_score"],
            validation=report,
        )
        QuestionnaireRepository(self.db).add(q)
        self.db.commit()
        self.db.refresh(q)
        return q
