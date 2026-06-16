"""Single entry point that dispatches to deterministic statistical routines."""
from __future__ import annotations

import pandas as pd

from app.analytics.anova import one_way_anova
from app.analytics.correlation import correlation_analysis
from app.analytics.descriptive import descriptive_statistics
from app.analytics.frequency import frequency_distribution
from app.analytics.plspm import run_plspm
from app.analytics.regression import linear_regression
from app.analytics.reliability import reliability_analysis


class AnalyticsEngine:
    """Stateless engine. Methods accept a DataFrame and return JSON-safe dicts."""

    SUPPORTED = (
        "descriptive",
        "correlation",
        "regression",
        "anova",
        "frequency",
        "reliability",
        "plspm",
    )

    def run(self, analysis_type: str, df: pd.DataFrame, **params) -> dict:
        if analysis_type not in self.SUPPORTED:
            raise ValueError(
                f"Unsupported analysis '{analysis_type}'. "
                f"Choose from {self.SUPPORTED}."
            )
        handler = getattr(self, f"_{analysis_type}")
        return handler(df, **params)

    def _reliability(self, df, constructs=None, **_):
        if not constructs:
            raise ValueError("Reliability analysis requires a `constructs` mapping.")
        return reliability_analysis(df, constructs)

    def _plspm(self, df, measurement=None, paths=None, bootstrap=300, **_):
        if not measurement or not paths:
            raise ValueError("PLS-PM requires `measurement` and `paths` model specifications.")
        return run_plspm(df, measurement, paths, bootstrap=bootstrap)

    # --- individual handlers -------------------------------------------------
    def _descriptive(self, df, columns=None, **_):
        return descriptive_statistics(df, columns)

    def _frequency(self, df, columns=None, **_):
        if not columns:
            raise ValueError("Frequency analysis requires `columns`.")
        return frequency_distribution(df, columns)

    def _correlation(self, df, columns=None, method="pearson", **_):
        return correlation_analysis(df, columns, method)

    def _regression(self, df, dependent=None, independents=None, **_):
        return linear_regression(df, dependent, independents or [])

    def _anova(self, df, dependent=None, group_column=None, **_):
        if not dependent or not group_column:
            raise ValueError("ANOVA requires `dependent` and `group_column`.")
        return one_way_anova(df, dependent, group_column)
