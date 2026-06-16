from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def jsonable(value: Any) -> Any:
    """Recursively convert numpy/pandas types into JSON-serialisable Python."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.ndarray,)):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, (pd.Series,)):
        return jsonable(value.to_dict())
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    return value


def numeric_columns(df: pd.DataFrame, columns: list[str] | None = None) -> list[str]:
    candidates = columns or list(df.columns)
    return [c for c in candidates if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]


def require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found in dataset: {missing}")
