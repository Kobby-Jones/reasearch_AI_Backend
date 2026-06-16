"""Whole-project analysis orchestration.

Given a project (objectives, hypotheses, variables, questionnaire) and one of its
uploaded datasets, this service runs the *standard quantitative battery* a
survey-based study needs and persists each step as an ``AnalysisResult`` so the
report generator can weave them into Chapter Four.

The battery, in order:
    1. Reliability (Cronbach's alpha) for every multi-item construct.
    2. Composite construct scores (row means) added to the working frame.
    3. Descriptive statistics of the composite constructs.
    4. Frequency distributions of demographic (categorical) items.
    5. Correlations among the composite constructs.
    6. Regression of the dependent construct on the independent constructs
       (the omnibus test of the study's core hypotheses).
    7. One-way ANOVA of the dependent construct across each demographic group
       (covers "differs across groups" hypotheses).

Every number is produced by the deterministic :class:`AnalyticsEngine`; no AI is
involved here.  Column/construct mapping is taken from the project's saved
questionnaire structure and is intersected with the columns that are actually
present in the dataset, so a partially-matching upload degrades gracefully
rather than failing.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.analytics.engine import AnalyticsEngine
from app.core.exceptions import NotFoundError, ValidationError
from app.models.analysis import AnalysisResult
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.utils.dataset_loader import load_dataframe
from app.utils.usage_tracker import UsageTracker, ANALYSIS_RUNS

# how a construct's composite score column is named in the working frame
_COMPOSITE_SUFFIX = "_score"


def _slug(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()
    return s or "construct"


class AutoAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.datasets = DatasetRepository(db)
        self.results = AnalysisRepository(db)
        self.engine = AnalyticsEngine()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)

    # ------------------------------------------------------------------ public
    def propose_plan(self, user_id: int, project_id: int, dataset_id: int) -> dict:
        """Detect the analysis plan WITHOUT running anything or consuming quota.

        Returns the construct->columns mapping, demographic columns, the inferred
        structural model, and the full column inventory, so the user can review
        and correct it before committing to a run.
        """
        project = self.research.get_owned(project_id, user_id)
        dataset = self.datasets.get(dataset_id)
        if not dataset or dataset.project_id != project.id:
            raise NotFoundError("Dataset not found for this project.")
        df = load_dataframe(dataset.storage_path)
        if df is None or df.empty:
            raise ValidationError("The dataset is empty.")

        constructs, demographics = self._mapping(project, df)
        structural = self._detect_structural(project, constructs)
        all_cols = []
        for col in df.columns:
            series = df[col]
            try:
                import pandas as pd  # local
                numeric = bool(pd.api.types.is_numeric_dtype(series))
            except Exception:
                numeric = False
            all_cols.append({
                "name": str(col),
                "numeric": numeric,
                "unique": int(series.nunique(dropna=True)),
            })
        return {
            "project_id": project.id,
            "dataset_id": dataset.id,
            "n_observations": int(len(df)),
            "columns": all_cols,
            "constructs": {c: cols for c, cols in constructs.items()},
            "demographics": demographics,
            "structural": structural,  # {"outcome": str|None, "predictors": [..]}
        }

    def run_full(
        self, user_id: int, project_id: int, dataset_id: int, plan: dict | None = None
    ) -> dict:
        gate = FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)
        gate.check_analysis()

        project = self.research.get_owned(project_id, user_id)
        dataset = self.datasets.get(dataset_id)
        if not dataset or dataset.project_id != project.id:
            raise NotFoundError("Dataset not found for this project.")

        df = load_dataframe(dataset.storage_path)
        if df is None or df.empty:
            raise ValidationError("The dataset is empty.")

        self.tracker.increment(user_id, ANALYSIS_RUNS)

        # Use the user-confirmed plan when provided; otherwise auto-detect.
        if plan:
            constructs, demographics, structural = self._apply_plan(plan, df)
        else:
            constructs, demographics = self._mapping(project, df)
            structural = self._detect_structural(project, constructs)

        steps: list[dict] = []
        skipped: list[str] = []

        # 1. reliability ------------------------------------------------------
        multi_item = {c: cols for c, cols in constructs.items() if len(cols) >= 2}
        if multi_item:
            res = self.engine.run("reliability", df, constructs=multi_item)
            self._persist(dataset.id, "reliability", {"constructs": multi_item}, res)
            steps.append({"type": "reliability", "constructs": list(multi_item)})
        else:
            skipped.append("reliability (no multi-item constructs detected)")

        # 2. composite construct scores --------------------------------------
        composite_cols: dict[str, str] = {}
        for c, cols in constructs.items():
            if not cols:
                continue
            col_name = f"{_slug(c)}{_COMPOSITE_SUFFIX}"
            df[col_name] = df[cols].mean(axis=1, numeric_only=True)
            composite_cols[c] = col_name

        # 3. descriptive of composites ---------------------------------------
        if composite_cols:
            cols = list(composite_cols.values())
            res = self.engine.run("descriptive", df, columns=cols)
            self._persist(dataset.id, "descriptive", {"columns": cols}, res)
            steps.append({"type": "descriptive", "columns": list(composite_cols)})

        # 4. demographic frequencies -----------------------------------------
        if demographics:
            res = self.engine.run("frequency", df, columns=demographics)
            self._persist(dataset.id, "frequency", {"columns": demographics}, res)
            steps.append({"type": "frequency", "columns": demographics})
        else:
            skipped.append("frequency (no demographic columns detected)")

        # 5. correlations among composites -----------------------------------
        if len(composite_cols) >= 2:
            cols = list(composite_cols.values())
            res = self.engine.run("correlation", df, columns=cols, method="pearson")
            self._persist(dataset.id, "correlation", {"columns": cols}, res)
            steps.append({"type": "correlation", "columns": list(composite_cols)})

        # 6. regression: DV ~ IVs --------------------------------------------
        dep = structural.get("outcome")
        dep_col = composite_cols.get(dep) if dep else None
        indeps = [composite_cols[p] for p in structural.get("predictors", []) if p in composite_cols]
        if dep_col and indeps:
            res = self.engine.run(
                "regression", df, dependent=dep_col, independents=indeps
            )
            self._persist(
                dataset.id, "regression",
                {"dependent": dep_col, "independents": indeps}, res,
            )
            steps.append({"type": "regression", "dependent": dep, "independents": structural.get("predictors", [])})
        else:
            skipped.append("regression (could not identify dependent + independent constructs)")

        # 7. ANOVA: DV across each demographic group -------------------------
        if dep_col and demographics:
            for g in demographics:
                try:
                    res = self.engine.run(
                        "anova", df, dependent=dep_col, group_column=g
                    )
                except ValueError:
                    continue
                self._persist(
                    dataset.id, "anova",
                    {"dependent": dep_col, "group_column": g}, res,
                )
                steps.append({"type": "anova", "dependent": dep, "group_column": g})

        # 8. PLS-PM structural model -----------------------------------------
        plspm_step = self._run_plspm(df, constructs, structural, dataset.id)
        if plspm_step:
            steps.append(plspm_step)
        else:
            skipped.append("plspm (no multi-item structural model with >=2 predictors)")

        self.db.commit()
        return {
            "project_id": project.id,
            "dataset_id": dataset.id,
            "n_observations": int(len(df)),
            "constructs_detected": {c: cols for c, cols in constructs.items()},
            "demographics_detected": demographics,
            "steps_run": steps,
            "skipped": skipped,
        }

    # ------------------------------------------------------- structural model
    def _detect_structural(self, project, constructs: dict[str, list[str]]) -> dict:
        """Infer {outcome, predictors} (construct names) from project variables."""
        measurement = [c for c, cols in constructs.items() if len(cols) >= 2]
        v = project.variables or {}
        if not isinstance(v, dict) or len(measurement) < 2:
            return {"outcome": None, "predictors": []}

        def names(key):
            val = v.get(key)
            if isinstance(val, str):
                return [val]
            if isinstance(val, list):
                return [str(x) for x in val]
            return []

        def match(name):
            for c in measurement:
                if c.lower().strip() == name.lower().strip() or name.lower() in c.lower():
                    return c
            return None

        outcome = None
        for n in names("dependent"):
            outcome = match(n)
            if outcome:
                break
        predictors = []
        for n in names("independent") + names("mediating") + names("moderating"):
            c = match(n)
            if c and c != outcome and c not in predictors:
                predictors.append(c)

        if (not outcome or len(predictors) < 2) and len(measurement) >= 3:
            outcome = outcome or measurement[-1]
            predictors = [c for c in measurement if c != outcome]
        return {"outcome": outcome, "predictors": predictors}

    def _apply_plan(self, plan: dict, df):
        """Resolve a user-confirmed plan, keeping only columns present in the data."""
        cols_present = {str(c) for c in df.columns}
        constructs = {}
        for name, cols in (plan.get("constructs") or {}).items():
            kept = [c for c in cols if c in cols_present]
            if kept:
                constructs[name] = kept
        demographics = [c for c in (plan.get("demographics") or []) if c in cols_present]
        structural = plan.get("structural") or {"outcome": None, "predictors": []}
        # keep only predictors/outcome that are valid constructs
        valid = set(constructs.keys())
        structural = {
            "outcome": structural.get("outcome") if structural.get("outcome") in valid else None,
            "predictors": [p for p in structural.get("predictors", []) if p in valid],
        }
        return constructs, demographics, structural

    def _run_plspm(self, df, constructs: dict[str, list[str]], structural: dict, dataset_id: int):
        """Fit PLS-PM from the resolved structural plan, if feasible."""
        measurement = {c: cols for c, cols in constructs.items() if len(cols) >= 2}
        outcome = structural.get("outcome")
        predictors = [p for p in structural.get("predictors", []) if p in measurement]
        if not outcome or outcome not in measurement or len(predictors) < 2:
            return None
        paths = {outcome: predictors}
        try:
            res = self.engine.run("plspm", df, measurement=measurement, paths=paths, bootstrap=300)
        except Exception:
            return None
        self._persist(dataset_id, "plspm", {"measurement": measurement, "paths": paths}, res)
        return {"type": "plspm", "outcome": outcome, "predictors": predictors}

    # ----------------------------------------------------------------- mapping
    def _mapping(self, project, df) -> tuple[dict[str, list[str]], list[str]]:
        """Return (construct -> existing item columns, demographic columns)."""
        existing = {str(c): c for c in df.columns}
        existing_lower = {str(c).lower(): c for c in df.columns}

        def resolve(code) -> str | None:
            code = str(code)
            if code in existing:
                return existing[code]
            return existing_lower.get(code.lower())

        constructs: dict[str, list[str]] = {}
        demographics: list[str] = []

        questionnaires = getattr(project, "questionnaires", []) or []
        structure = None
        if questionnaires:
            # most recent questionnaire wins
            structure = sorted(questionnaires, key=lambda q: q.id)[-1].structure

        if structure and isinstance(structure, dict):
            for section in structure.get("sections", []):
                construct = section.get("construct") or section.get("title") or ""
                items = section.get("items", [])
                if str(construct).strip().lower() in ("demographics", "demographic"):
                    for it in items:
                        col = resolve(it.get("id")) or resolve(it.get("text"))
                        if col is not None and col not in demographics:
                            demographics.append(col)
                    continue
                cols = []
                for it in items:
                    col = resolve(it.get("id"))
                    if col is not None:
                        cols.append(col)
                if cols:
                    constructs[str(construct)] = cols

        # Fallback: no questionnaire mapping resolved — infer from dtypes.
        if not constructs:
            constructs, demographics = self._infer_from_dtypes(df)

        return constructs, demographics

    def _infer_from_dtypes(self, df):
        """Heuristic mapping when no questionnaire structure is available."""
        import pandas as pd  # local import keeps module import-light

        numeric, categorical = [], []
        for col in df.columns:
            series = df[col]
            if pd.api.types.is_numeric_dtype(series):
                # likert-like: small integer range
                uniques = series.dropna().unique()
                if len(uniques) <= 7 and series.dropna().between(1, 7).all():
                    numeric.append(col)
            else:
                if series.nunique(dropna=True) <= 10:
                    categorical.append(col)
        constructs = {"Composite Scale": numeric} if numeric else {}
        return constructs, categorical

    def _dv_iv(self, project, composite_cols: dict[str, str]):
        """Pick dependent + independent composite columns from project.variables."""
        v = project.variables or {}
        if not isinstance(v, dict):
            return None, []

        def names(key):
            val = v.get(key)
            if isinstance(val, str):
                return [val]
            if isinstance(val, list):
                return [str(x) for x in val]
            return []

        def match(name):
            # match a declared variable name to a composite construct column
            for c, col in composite_cols.items():
                if c.lower().strip() == name.lower().strip() or name.lower() in c.lower():
                    return col
            return None

        dep = None
        for n in names("dependent"):
            dep = match(n)
            if dep:
                break
        indeps = []
        for n in names("independent") + names("mediating") + names("moderating"):
            col = match(n)
            if col and col != dep and col not in indeps:
                indeps.append(col)

        # fallback: if we have composites but no declared mapping, use the last
        # as DV and the rest as IVs so the user still gets a model.
        if (not dep or not indeps) and len(composite_cols) >= 2:
            cols = list(composite_cols.values())
            dep = dep or cols[-1]
            indeps = indeps or [c for c in cols if c != dep]

        return dep, indeps

    # --------------------------------------------------------------- persistence
    def _persist(self, dataset_id: int, atype: str, params: dict, results: dict) -> None:
        record = AnalysisResult(
            dataset_id=dataset_id,
            analysis_type=atype,
            parameters=params,
            results=results,
        )
        self.results.add(record)
