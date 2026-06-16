from __future__ import annotations

import pandas as pd

from app.analytics._util import jsonable, require_columns


def frequency_distribution(df: pd.DataFrame, columns: list[str]) -> dict:
    require_columns(df, columns)
    out: dict = {"n_observations": int(len(df)), "variables": {}}
    for c in columns:
        counts = df[c].value_counts(dropna=False)
        total = int(counts.sum())
        rows = []
        for value, n in counts.items():
            label = "<<missing>>" if pd.isna(value) else value
            rows.append(
                {
                    "value": jsonable(label),
                    "count": int(n),
                    "percent": round(100.0 * int(n) / total, 2) if total else 0.0,
                }
            )
        out["variables"][c] = {
            "unique": int(df[c].nunique(dropna=True)),
            "distribution": rows,
            "chart": {
                "labels": [r["value"] for r in rows],
                "values": [r["count"] for r in rows],
            },
        }
    return jsonable(out)
