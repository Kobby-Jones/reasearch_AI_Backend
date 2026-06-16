from __future__ import annotations

import pandas as pd

from app.analytics._util import jsonable, numeric_columns


def descriptive_statistics(df: pd.DataFrame, columns: list[str] | None = None) -> dict:
    cols = numeric_columns(df, columns)
    if not cols:
        raise ValueError("No numeric columns available for descriptive statistics.")

    out: dict = {"n_observations": int(len(df)), "variables": {}}
    for c in cols:
        s = df[c].dropna()
        out["variables"][c] = {
            "count": int(s.count()),
            "missing": int(df[c].isna().sum()),
            "mean": float(s.mean()) if len(s) else None,
            "median": float(s.median()) if len(s) else None,
            "mode": jsonable(s.mode().tolist()[:3]),
            "std": float(s.std(ddof=1)) if len(s) > 1 else None,
            "variance": float(s.var(ddof=1)) if len(s) > 1 else None,
            "min": float(s.min()) if len(s) else None,
            "max": float(s.max()) if len(s) else None,
            "range": float(s.max() - s.min()) if len(s) else None,
            "q1": float(s.quantile(0.25)) if len(s) else None,
            "q3": float(s.quantile(0.75)) if len(s) else None,
            "skewness": float(s.skew()) if len(s) > 2 else None,
            "kurtosis": float(s.kurt()) if len(s) > 3 else None,
        }
    return jsonable(out)
