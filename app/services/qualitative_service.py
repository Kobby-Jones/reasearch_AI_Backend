"""Qualitative analysis workflow (thematic analysis of free-text data)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.thematic import run_thematic
from app.core.exceptions import NotFoundError, ValidationError
from app.models.analysis import AnalysisResult
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.study_profile import summarize_dataset
from app.services.subscription_service import SubscriptionService
from app.ai.client import get_ai_client
from app.utils.dataset_loader import load_dataframe
from app.utils.usage_tracker import UsageTracker, ANALYSIS_RUNS, AI_CALLS


class _AICoder:
    """Adapts the AI client to the ThematicCoder protocol, batching the coding."""

    def __init__(self, ai, context: dict, tracker: UsageTracker, user_id: int, batch: int = 20):
        self.ai = ai
        self.context = context
        self.tracker = tracker
        self.user_id = user_id
        self.batch = batch

    def induce_themes(self, responses: list[str]) -> list[dict]:
        self.tracker.increment(self.user_id, AI_CALLS)
        return self.ai.induce_themes(responses, self.context)

    def code_responses(self, responses: list[str], themes: list[dict]) -> list[dict]:
        coded: list[dict] = []
        for start in range(0, len(responses), self.batch):
            chunk = responses[start:start + self.batch]
            self.tracker.increment(self.user_id, AI_CALLS)
            coded.extend(self.ai.code_responses_batch(chunk, themes, self.context))
        return coded


class QualitativeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)
        self.ai = get_ai_client()

    def run(self, user_id: int, project_id: int, dataset_id: int,
            text_columns: list[str] | None = None) -> dict:
        gate = FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)
        gate.check_analysis()

        project = self.research.get_owned(project_id, user_id)
        dataset = self.datasets.get(dataset_id)
        if not dataset or dataset.project_id != project.id:
            raise NotFoundError("Dataset not found for this project.")

        df = load_dataframe(dataset.storage_path)
        if df is None or df.empty:
            raise ValidationError("The dataset is empty.")

        # choose the free-text columns (caller override, else auto-detected)
        if not text_columns:
            summary = summarize_dataset(df)
            text_columns = [c for c, kind in summary["columns"].items() if kind == "free_text"]
        text_columns = [c for c in (text_columns or []) if c in df.columns]
        if not text_columns:
            raise ValidationError(
                "No free-text columns found for thematic analysis. "
                "Upload open-ended responses or pick the text column(s) explicitly."
            )

        # pool responses across the chosen text columns
        responses: list[str] = []
        for col in text_columns:
            responses.extend(str(v).strip() for v in df[col].dropna() if str(v).strip())

        self.tracker.increment(user_id, ANALYSIS_RUNS)
        context = {
            "topic": project.topic, "field": project.field,
            "objectives": project.objectives, "text_columns": text_columns,
        }
        coder = _AICoder(self.ai, context, self.tracker, user_id)
        result = run_thematic(responses, coder)
        result["text_columns"] = text_columns

        self._persist(dataset.id, "thematic", {"text_columns": text_columns}, result)
        self.db.commit()
        return {
            "project_id": project.id,
            "dataset_id": dataset.id,
            "text_columns": text_columns,
            "n_responses": result["n_responses"],
            "n_themes": result["n_themes"],
            "themes": [t["name"] for t in result["themes"]],
        }

    def _persist(self, dataset_id: int, atype: str, params: dict, results: dict) -> None:
        self.results.add(AnalysisResult(
            dataset_id=dataset_id, analysis_type=atype,
            parameters=params, results=results,
        ))
