"""Study-type classification.

Decides what *kind* of study a project is, so the platform can route it to an
analysis workflow built for that kind instead of assuming every project is a
quantitative survey. The result is always a *proposal* the student can override.

Five types cover the student population without overlap:

- ``quantitative_survey``  Likert constructs, reliability, correlation/regression, PLS-PM.
- ``qualitative``          interviews / open text -> thematic analysis (codes, themes, quotes).
- ``mixed_methods``        both quantitative and qualitative strands, integrated.
- ``secondary_data``       numeric dataset that is not a survey (indicators, measurements, time series).
- ``literature_review``    no primary data; synthesis of sources.

Classification is transparent: every type accumulates a score from named
signals, and those reasons are returned so the UI can explain the choice.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

STUDY_TYPES = {
    "quantitative_survey": "Quantitative survey",
    "qualitative": "Qualitative study",
    "mixed_methods": "Mixed methods",
    "secondary_data": "Secondary data analysis",
    "literature_review": "Literature review / conceptual",
}

# recommended workflow per type (consumed by the analysis router)
WORKFLOWS = {
    "quantitative_survey": "survey_battery",
    "qualitative": "thematic_analysis",
    "mixed_methods": "mixed",
    "secondary_data": "data_exploration",
    "literature_review": "synthesis",
}

_KEYWORDS = {
    "qualitative": [
        "qualitative", "thematic analysis", "interview", "focus group", "open-ended",
        "open ended", "phenomenolog", "grounded theory", "ethnograph", "narrative inquiry",
        "in-depth", "lived experience", "semi-structured", "nvivo", "atlas.ti", "coding",
    ],
    "quantitative_survey": [
        "quantitative", "survey", "questionnaire", "likert", "regression", "correlation",
        "pls-pm", "pls", "sem", "structural equation", "cronbach", "hypothes", "construct",
        "factor analysis", "sample size", "respondents",
    ],
    "mixed_methods": [
        "mixed method", "mixed-method", "convergent", "explanatory sequential",
        "exploratory sequential", "triangulat", "qual and quant", "quant and qual",
    ],
    "secondary_data": [
        "secondary data", "time series", "time-series", "panel data", "econometric",
        "administrative data", "dataset obtained", "existing data", "world bank data",
        "official statistics", "experimental data", "measurements", "sensor",
    ],
    "literature_review": [
        "literature review", "systematic review", "meta-analysis", "meta analysis",
        "scoping review", "conceptual paper", "desk study", "desk-based", "narrative review",
        "bibliometric", "no primary data",
    ],
}


@dataclass
class StudyProfile:
    study_type: str
    confidence: float
    reasons: list[str]
    scores: dict[str, float]
    workflow: str
    available_types: dict[str, str] = field(default_factory=lambda: dict(STUDY_TYPES))

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_type": self.study_type,
            "study_type_label": STUDY_TYPES.get(self.study_type, self.study_type),
            "confidence": round(self.confidence, 2),
            "reasons": self.reasons,
            "scores": {k: round(v, 2) for k, v in self.scores.items()},
            "workflow": self.workflow,
            "available_types": self.available_types,
        }


# ---------------------------------------------------------------------------
# dataset characterisation
# ---------------------------------------------------------------------------
def summarize_dataset(df: pd.DataFrame, *, sample: int = 200) -> dict[str, Any]:
    """Classify each column into a 'kind' so the study type can be inferred."""
    n = len(df)
    head = df.head(sample)
    kinds: Counter = Counter()
    col_kinds: dict[str, str] = {}
    for col in df.columns:
        s = df[col]
        kind = _column_kind(s, head[col], n)
        col_kinds[str(col)] = kind
        kinds[kind] += 1
    return {"n_rows": int(n), "n_cols": int(df.shape[1]), "kinds": dict(kinds), "columns": col_kinds}


def _column_kind(s: pd.Series, head: pd.Series, n: int) -> str:
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        nun = s.nunique(dropna=True)
        vals = pd.to_numeric(s, errors="coerce").dropna()
        if not vals.empty and nun <= 7 and float(vals.min()) >= 1 and float(vals.max()) <= 7 and (vals == vals.round()).all():
            return "likert"
        return "numeric"
    # object / text
    nun = s.nunique(dropna=True)
    uniq_ratio = nun / n if n else 0
    text = head.dropna().astype(str)
    avg_len = float(text.str.len().mean()) if not text.empty else 0.0
    if avg_len >= 40 or (avg_len >= 18 and uniq_ratio >= 0.6):
        return "free_text"
    if uniq_ratio >= 0.95 and avg_len <= 20:
        return "identifier"
    return "categorical"


# ---------------------------------------------------------------------------
# classifier
# ---------------------------------------------------------------------------
def classify_study(
    *,
    text_signals: str,
    has_hypotheses: bool,
    has_questionnaire: bool,
    has_multi_item_constructs: bool,
    datasets: list[dict[str, Any]],
) -> StudyProfile:
    scores: dict[str, float] = {k: 0.0 for k in STUDY_TYPES}
    reasons: list[str] = []
    text = (text_signals or "").lower()

    # --- 1. declared-methodology keywords ---
    for stype, words in _KEYWORDS.items():
        hits = [w for w in words if w in text]
        if hits:
            scores[stype] += 1.2 * len(hits[:3])  # cap influence of any one bucket
            reasons.append(f"Methodology text mentions {', '.join(hits[:3])} ({STUDY_TYPES[stype]}).")

    # --- 2. data-shape evidence ---
    total_free = sum(d["kinds"].get("free_text", 0) for d in datasets)
    total_likert = sum(d["kinds"].get("likert", 0) for d in datasets)
    total_numeric = sum(d["kinds"].get("numeric", 0) for d in datasets)
    has_data = bool(datasets)

    if total_free >= 1:
        scores["qualitative"] += 2.0 + min(total_free, 5) * 0.3
        reasons.append(f"Dataset has {total_free} free-text column(s), suited to thematic analysis.")
    if total_likert >= 3:
        scores["quantitative_survey"] += 2.0
        reasons.append(f"Dataset has {total_likert} Likert-scale columns.")
    if total_numeric >= 3 and total_likert == 0 and not has_questionnaire:
        scores["secondary_data"] += 2.0
        reasons.append(f"Dataset is mostly numeric ({total_numeric} measures) with no survey instrument.")

    # --- 3. instrument & design evidence ---
    if has_questionnaire:
        scores["quantitative_survey"] += 1.5
        reasons.append("A questionnaire instrument is attached.")
    if has_multi_item_constructs:
        scores["quantitative_survey"] += 1.0
        reasons.append("Multi-item reflective constructs are defined.")
    if has_hypotheses:
        scores["quantitative_survey"] += 0.6
        scores["secondary_data"] += 0.3
        reasons.append("The study states testable hypotheses.")

    # --- 4. mixed-methods: both strands present ---
    qual_strength = scores["qualitative"]
    quant_strength = scores["quantitative_survey"] + scores["secondary_data"]
    if qual_strength >= 2 and quant_strength >= 2:
        scores["mixed_methods"] += min(qual_strength, quant_strength) + 1.0
        reasons.append("Both qualitative and quantitative strands are present, indicating a mixed design.")

    # --- 5. literature review: no primary data at all ---
    if not has_data and not has_questionnaire:
        scores["literature_review"] += 2.5
        reasons.append("No primary dataset or instrument was provided, consistent with a literature or conceptual review.")

    # decide
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        best = "quantitative_survey"  # safe default; user can change
        reasons.append("No strong signal; defaulting to quantitative survey (you can change this).")
    total = sum(v for v in scores.values() if v > 0) or 1.0
    confidence = scores[best] / total

    return StudyProfile(
        study_type=best,
        confidence=confidence,
        reasons=reasons,
        scores=scores,
        workflow=WORKFLOWS[best],
    )
