from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.engine import AnalyticsEngine
from app.ai.client import get_ai_client
from app.core.exceptions import NotFoundError, ValidationError
from app.models.analysis import AnalysisResult
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.utils.dataset_loader import load_dataframe
from app.utils.usage_tracker import UsageTracker, AI_CALLS, ANALYSIS_RUNS


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)
        self.engine = AnalyticsEngine()
        self.ai = get_ai_client()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)

    def _gate(self, user_id: int) -> FeatureGate:
        return FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)

    def run(self, user_id: int, params: dict) -> AnalysisResult:
        gate = self._gate(user_id)
        gate.check_analysis()  # plan-based restriction

        dataset = self.datasets.get(params["dataset_id"])
        if not dataset or dataset.project.user_id != user_id:
            raise NotFoundError("Dataset not found.")

        df = load_dataframe(dataset.storage_path)
        analysis_type = params["analysis_type"]

        try:
            # ALL numbers computed here, deterministically. No AI involved.
            results = self.engine.run(
                analysis_type,
                df,
                columns=params.get("columns"),
                method=params.get("method", "pearson"),
                dependent=params.get("dependent"),
                independents=params.get("independents"),
                group_column=params.get("group_column"),
                constructs=params.get("constructs"),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        self.tracker.increment(user_id, ANALYSIS_RUNS)

        record = AnalysisResult(
            dataset_id=dataset.id,
            analysis_type=analysis_type,
            parameters={k: v for k, v in params.items() if k != "dataset_id"},
            results=results,
        )
        self.results.add(record)
        self.db.commit()
        return record

    def interpret(self, user_id: int, analysis_id: int, style: str) -> AnalysisResult:
        record = self.results.get(analysis_id)
        if not record or record.dataset.project.user_id != user_id:
            raise NotFoundError("Analysis result not found.")

        gate = self._gate(user_id)
        advanced = style == "advanced"
        if advanced:
            gate.check_advanced_interpretation()  # PREMIUM only

        # AI only turns already-computed numbers into prose.
        text = self.ai.analyze_research(record.analysis_type, record.results, advanced=advanced)
        self.tracker.increment(user_id, AI_CALLS)

        record.interpretation = text
        self.db.commit()
        return record

    def list(
        self,
        user_id: int,
        dataset_id: int | None = None,
        project_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AnalysisResult]:
        if dataset_id is None and project_id is None:
            raise ValidationError("Provide either dataset_id or project_id.")
        if dataset_id is not None:
            dataset = self.datasets.get(dataset_id)
            if not dataset or dataset.project.user_id != user_id:
                raise NotFoundError("Dataset not found.")
            return self.results.list_for_dataset(dataset_id, limit=limit, offset=offset)
        # project-scoped: verify ownership before listing across its datasets
        ResearchService(self.db).get_owned(project_id, user_id)
        return self.results.list_for_project(project_id, limit=limit, offset=offset)