from __future__ import annotations

from itertools import combinations

import pandas as pd
from scipy import stats

from app.analytics._util import jsonable, numeric_columns


def correlation_analysis(
    df: pd.DataFrame, columns: list[str] | None = None, method: str = "pearson"
) -> dict:
    if method not in {"pearson", "spearman"}:
        raise ValueError("method must be 'pearson' or 'spearman'")
    cols = numeric_columns(df, columns)
    if len(cols) < 2:
        raise ValueError("Correlation requires at least two numeric columns.")

    pairs = []
    for a, b in combinations(cols, 2):
        sub = df[[a, b]].dropna()
        if len(sub) < 3:
            continue
        if method == "pearson":
            r, p = stats.pearsonr(sub[a], sub[b])
        else:
            r, p = stats.spearmanr(sub[a], sub[b])
        pairs.append(
            {
                "variable_a": a,
                "variable_b": b,
                "coefficient": float(r),
                "p_value": float(p),
                "n": int(len(sub)),
                "significant": bool(p < 0.05),
                "strength": _strength(abs(r)),
                "direction": "positive" if r >= 0 else "negative",
            }
        )

    matrix = df[cols].corr(method=method)
    from app.analytics.assumptions import correlation_assumptions
    assumptions = correlation_assumptions(df, cols, method)
    return jsonable(
        {
            "method": method,
            "pairs": pairs,
            "matrix": {"columns": cols, "values": matrix.values.tolist()},
            "assumptions": assumptions,
        }
    )


def _strength(abs_r: float) -> str:
    if abs_r < 0.1:
        return "negligible"
    if abs_r < 0.3:
        return "weak"
    if abs_r < 0.5:
        return "moderate"
    if abs_r < 0.7:
        return "strong"
    return "very strong"
