"""Load + clean uploaded datasets (CSV / Excel). SPSS .sav exports should be
saved as CSV/XLSX before upload (documented in README)."""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd


def load_dataframe(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if ext in {".tsv", ".txt"}:
        return pd.read_csv(path, sep="\t")
    raise ValueError(f"Unsupported file type '{ext}'. Use CSV or Excel.")


def detect_schema(df: pd.DataFrame) -> dict[str, Any]:
    schema = {}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            dtype = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            dtype = "datetime"
        else:
            dtype = "categorical"
        schema[str(col)] = {
            "dtype": dtype,
            "missing": int(s.isna().sum()),
            "unique": int(s.nunique(dropna=True)),
        }
    return schema


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Conservative cleaning: trim, coerce numerics, impute missing values."""
    report: dict[str, Any] = {"steps": [], "imputed": {}}
    before_rows = len(df)

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # drop fully-empty rows/columns
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if len(df) != before_rows:
        report["steps"].append(f"Dropped {before_rows - len(df)} empty rows.")

    for col in df.columns:
        if df[col].dtype == object:
            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().mean() >= 0.9:  # mostly numeric
                df[col] = coerced

    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            fill = float(df[col].median())
            df[col] = df[col].fillna(fill)
            report["imputed"][col] = {"strategy": "median", "value": fill, "count": missing}
        else:
            mode = df[col].mode(dropna=True)
            fill = mode.iloc[0] if len(mode) else "Unknown"
            df[col] = df[col].fillna(fill)
            report["imputed"][col] = {"strategy": "mode", "value": str(fill), "count": missing}

    report["final_rows"] = int(len(df))
    report["final_columns"] = int(df.shape[1])
    return df, report
