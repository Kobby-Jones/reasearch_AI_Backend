"""Service wrapper around the study-type classifier.

Gathers the real signals for a project (declared methodology, instrument,
hypotheses, and the actual shape of each uploaded dataset) and returns a
study-type proposal for the student to confirm or override.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.research_service import ResearchService
from app.services.study_profile import classify_study, summarize_dataset
from app.utils.dataset_loader import load_dataframe


class StudyTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.research = ResearchService(db)

    def propose(self, user_id: int, project_id: int) -> dict:
        project = self.research.get_owned(project_id, user_id)

        text_signals = self._text_signals(project)
        has_hypotheses = bool(project.hypotheses)
        has_questionnaire = bool(getattr(project, "questionnaires", None))
        has_multi = self._has_multi_item_constructs(project)
        datasets = self._dataset_summaries(project)

        profile = classify_study(
            text_signals=text_signals,
            has_hypotheses=has_hypotheses,
            has_questionnaire=has_questionnaire,
            has_multi_item_constructs=has_multi,
            datasets=datasets,
        )
        out = profile.to_dict()
        out["project_id"] = project.id
        out["data_summary"] = datasets
        return out

    # ------------------------------------------------------------------ signals
    def _text_signals(self, project) -> str:
        parts: list[str] = [project.topic or "", project.field or "", project.summary or ""]
        m = project.methodology
        if isinstance(m, dict):
            parts.extend(str(v) for v in m.values())
        elif isinstance(m, str):
            parts.append(m)
        for key in ("objectives", "hypotheses"):
            val = getattr(project, key, None)
            if isinstance(val, list):
                parts.extend(str(x) for x in val)
        return " \n ".join(p for p in parts if p)

    def _has_multi_item_constructs(self, project) -> bool:
        for q in getattr(project, "questionnaires", []) or []:
            structure = getattr(q, "structure", None) or {}
            for section in structure.get("sections", []):
                construct = (section.get("construct") or "").lower()
                items = section.get("items", [])
                if construct and construct != "demographics" and len(items) >= 2:
                    return True
        return False

    def _dataset_summaries(self, project) -> list[dict]:
        summaries: list[dict] = []
        for ds in getattr(project, "datasets", []) or []:
            try:
                df = load_dataframe(ds.storage_path)
            except Exception:
                df = None
            if df is None or df.empty:
                continue
            s = summarize_dataset(df)
            s["dataset_id"] = ds.id
            s["filename"] = getattr(ds, "filename", None)
            summaries.append(s)
        return summaries
