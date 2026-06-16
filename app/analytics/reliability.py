"""Scale-reliability analysis (Cronbach's alpha).

For questionnaire-based research this is mandatory: before any construct can be
used in correlation/regression/ANOVA, its multi-item scale must be shown to be
internally consistent. The AI never computes any of this — it is pure pandas /
numpy, consistent with the platform's deterministic-statistics principle.
"""
from __future__ import annotations

import pandas as pd

from app.analytics._util import jsonable, numeric_columns


def _alpha(frame: pd.DataFrame) -> float | None:
    """Standard Cronbach's alpha for a set of item columns."""
    items = frame.dropna()
    k = items.shape[1]
    if k < 2 or len(items) < 2:
        return None
    item_vars = items.var(axis=0, ddof=1)
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return None
    return float((k / (k - 1)) * (1 - item_vars.sum() / total_var))


def _interpret_alpha(a: float | None) -> str:
    if a is None:
        return "not computable"
    if a >= 0.9:
        return "excellent"
    if a >= 0.8:
        return "good"
    if a >= 0.7:
        return "acceptable"
    if a >= 0.6:
        return "questionable"
    if a >= 0.5:
        return "poor"
    return "unacceptable"


def reliability_analysis(
    df: pd.DataFrame, constructs: dict[str, list[str]]
) -> dict:
    """Compute Cronbach's alpha for each named construct.

    `constructs` maps a construct name to the list of item-column names that
    make up its scale, e.g. {"Motivation": ["B1", "B2", "B3"]}.
    Also reports alpha-if-item-deleted so weak items can be identified.
    """
    if not constructs:
        raise ValueError("Reliability analysis requires a construct→items mapping.")

    results: dict[str, dict] = {}
    for name, cols in constructs.items():
        usable = numeric_columns(df, cols)
        if len(usable) < 2:
            results[name] = {
                "n_items": len(usable),
                "alpha": None,
                "interpretation": "needs >= 2 numeric items",
                "items": usable,
            }
            continue

        frame = df[usable].apply(pd.to_numeric, errors="coerce")
        alpha = _alpha(frame)

        if_deleted = []
        for col in usable:
            remaining = [c for c in usable if c != col]
            a_wo = _alpha(frame[remaining]) if len(remaining) >= 2 else None
            if_deleted.append(
                {
                    "item": col,
                    "alpha_if_deleted": a_wo,
                    "improves_scale": bool(a_wo is not None and alpha is not None and a_wo > alpha),
                }
            )

        results[name] = {
            "n_items": len(usable),
            "n_cases": int(frame.dropna().shape[0]),
            "alpha": alpha,
            "interpretation": _interpret_alpha(alpha),
            "acceptable": bool(alpha is not None and alpha >= 0.7),
            "items": usable,
            "item_diagnostics": if_deleted,
        }

    return jsonable({"constructs": results})
