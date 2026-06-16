"""Literature-review / conceptual study workflow.

Builds a synthesis of REAL retrieved sources (themes + research gaps) for studies
that have no primary dataset. Because the analysis model attaches results to a
dataset, the literature corpus itself is recorded as a lightweight dataset row
(its "data" is the body of sources), under which the synthesis is persisted so it
flows through the normal report pipeline.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.client import get_ai_client
from app.ai.reference_client import build_project_library
from app.analytics.synthesis import build_synthesis
from app.core.exceptions import ValidationError
from app.models.analysis import AnalysisResult
from app.models.dataset import Dataset
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.utils.usage_tracker import UsageTracker, ANALYSIS_RUNS, AI_CALLS

_CORPUS_NAME = "Literature corpus"


class _AISynth:
    def __init__(self, ai, tracker, user_id):
        self.ai = ai
        self.tracker = tracker
        self.user_id = user_id

    def synthesize(self, catalog, topic, field):
        self.tracker.increment(self.user_id, AI_CALLS)
        return self.ai.synthesize_literature(catalog, topic, field)


class LiteratureReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)
        self.ai = get_ai_client()

    def run(self, user_id: int, project_id: int) -> dict:
        gate = FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)
        gate.check_analysis()

        project = self.research.get_owned(project_id, user_id)
        constructs = self._keywords(project)

        library = build_project_library(project.topic, project.field, constructs)
        if not library:
            raise ValidationError(
                "No sources could be retrieved for this topic. Check the topic wording, "
                "or that scholarly retrieval (OpenAlex) is reachable from the server."
            )

        self.tracker.increment(user_id, ANALYSIS_RUNS)
        synth = build_synthesis(library, project.topic, project.field,
                                _AISynth(self.ai, self.tracker, user_id))

        corpus = self._corpus_dataset(project, n_sources=synth["n_sources"])
        self.results.add(AnalysisResult(
            dataset_id=corpus.id, analysis_type="synthesis",
            parameters={"topic": project.topic}, results=synth,
        ))
        self.db.commit()
        return {
            "project_id": project.id,
            "dataset_id": corpus.id,
            "n_observations": synth["n_sources"],
            "constructs_detected": {},
            "demographics_detected": [],
            "steps_run": [{"type": "synthesis", "themes": [t["name"] for t in synth["themes"]]}],
            "skipped": [],
        }

    # ------------------------------------------------------------------ helpers
    def _keywords(self, project) -> list[str]:
        out: list[str] = []
        v = project.variables or {}
        if isinstance(v, dict):
            for group in v.values():
                if isinstance(group, list):
                    out.extend(str(x) for x in group)
                elif group:
                    out.append(str(group))
        return out[:6]

    def _corpus_dataset(self, project, n_sources: int) -> Dataset:
        for ds in getattr(project, "datasets", []) or []:
            if getattr(ds, "filename", "") == _CORPUS_NAME:
                ds.row_count = n_sources
                return ds
        return self.datasets.add(Dataset(
            project_id=project.id, filename=_CORPUS_NAME, storage_path="",
            row_count=n_sources, column_count=0,
            schema_info={"kind": "literature_corpus"},
        ))
