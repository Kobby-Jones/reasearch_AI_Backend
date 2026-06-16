"""Secondary-data analysis workflow.

For studies whose data is an existing numeric dataset (indicators, measurements,
time series, administrative records), not a survey. It runs the parts of the
battery that make sense for raw variables, deliberately WITHOUT the
construct/reliability/PLS-PM framing, which only applies to multi-item survey
instruments.

Steps:
    1. Descriptive statistics of numeric variables.
    2. Frequency distributions of categorical variables.
    3. Correlations among numeric variables.
    4. Regression of the dependent variable (from the study design, matched to a
       numeric column) on the other numeric variables.
    5. One-way ANOVA of the dependent across each categorical grouping.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.engine import AnalyticsEngine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.analysis import AnalysisResult
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.study_profile import summarize_dataset
from app.services.subscription_service import SubscriptionService
from app.utils.dataset_loader import load_dataframe
from app.utils.usage_tracker import UsageTracker, ANALYSIS_RUNS


class SecondaryDataService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)
        self.engine = AnalyticsEngine()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)

    def run(self, user_id: int, project_id: int, dataset_id: int,
            dependent: str | None = None) -> dict:
        gate = FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)
        gate.check_analysis()

        project = self.research.get_owned(project_id, user_id)
        dataset = self.datasets.get(dataset_id)
        if not dataset or dataset.project_id != project.id:
            raise NotFoundError("Dataset not found for this project.")

        df = load_dataframe(dataset.storage_path)
        if df is None or df.empty:
            raise ValidationError("The dataset is empty.")

        summary = summarize_dataset(df)
        kinds = summary["columns"]
        numeric = [c for c, k in kinds.items() if k in ("numeric", "likert")]
        categorical = [c for c, k in kinds.items() if k == "categorical"]

        self.tracker.increment(user_id, ANALYSIS_RUNS)
        steps: list[dict] = []
        skipped: list[str] = []

        # 1. descriptives
        if numeric:
            res = self.engine.run("descriptive", df, columns=numeric)
            self._persist(dataset.id, "descriptive", {"columns": numeric}, res)
            steps.append({"type": "descriptive", "columns": numeric})
        else:
            skipped.append("descriptive (no numeric columns)")

        # 2. frequency of categoricals
        if categorical:
            res = self.engine.run("frequency", df, columns=categorical)
            self._persist(dataset.id, "frequency", {"columns": categorical}, res)
            steps.append({"type": "frequency", "columns": categorical})

        # 3. correlation among numerics
        if len(numeric) >= 2:
            res = self.engine.run("correlation", df, columns=numeric)
            self._persist(dataset.id, "correlation", {"columns": numeric}, res)
            steps.append({"type": "correlation", "columns": numeric})

        # 4. regression: dependent ~ other numerics
        dep = self._pick_dependent(project, dependent, numeric)
        if dep and len([c for c in numeric if c != dep]) >= 1:
            indeps = [c for c in numeric if c != dep]
            res = self.engine.run("regression", df, dependent=dep, independents=indeps)
            self._persist(dataset.id, "regression", {"dependent": dep, "independents": indeps}, res)
            steps.append({"type": "regression", "dependent": dep, "independents": indeps})
        else:
            skipped.append("regression (no dependent numeric variable identified)")

        # 5. ANOVA: dependent across each categorical
        if dep and categorical:
            for g in categorical[:5]:
                try:
                    res = self.engine.run("anova", df, dependent=dep, group_column=g)
                except ValueError:
                    continue
                self._persist(dataset.id, "anova", {"dependent": dep, "group_column": g}, res)
                steps.append({"type": "anova", "dependent": dep, "group_column": g})

        self.db.commit()
        return {
            "project_id": project.id,
            "dataset_id": dataset.id,
            "n_observations": int(len(df)),
            "constructs_detected": {},
            "demographics_detected": categorical,
            "steps_run": steps,
            "skipped": skipped,
        }

    # ------------------------------------------------------------------ helpers
    def _pick_dependent(self, project, override: str | None, numeric: list[str]) -> str | None:
        if override and override in numeric:
            return override
        v = project.variables or {}
        if isinstance(v, dict):
            dep = v.get("dependent")
            names = dep if isinstance(dep, list) else [dep] if dep else []
            for name in names:
                for c in numeric:
                    if str(name).lower().strip() == c.lower().strip() or str(name).lower() in c.lower():
                        return c
        return None

    def _persist(self, dataset_id: int, atype: str, params: dict, results: dict) -> None:
        self.results.add(AnalysisResult(
            dataset_id=dataset_id, analysis_type=atype, parameters=params, results=results,
        ))
