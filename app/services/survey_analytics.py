"""Deterministic per-question response analytics for a survey.

Turns collected responses into the kind of at-a-glance summaries researchers
expect from Google Forms: counts per option, Likert distributions with a mean,
numeric summary stats with a histogram, and sampled free-text answers. No AI.
"""
from __future__ import annotations

import statistics
from collections import Counter

_CHOICE = {"single_choice", "dropdown"}
_AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]


def _column_id(item: dict, s_idx: int, i_idx: int) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or f"s{s_idx + 1}_{i_idx + 1}")
    return f"s{s_idx + 1}_{i_idx + 1}"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _histogram(values: list[float], bins: int = 8) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [{"label": _fmt(lo), "count": len(values)}]
    width = (hi - lo) / bins
    edges = [lo + i * width for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return [{"label": f"{_fmt(edges[i])}–{_fmt(edges[i + 1])}", "count": counts[i]} for i in range(bins)]


def _fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


def summarize_question(item: dict, values: list) -> dict:
    """Summarise the answers to one question. `values` excludes blanks."""
    qtype = item.get("type") or "likert"
    n = len(values)
    base = {
        "id": item.get("id"),
        "text": item.get("text", ""),
        "type": qtype,
        "response_count": n,
    }

    if qtype in _CHOICE or qtype == "yes_no":
        options = item.get("options") or (["Yes", "No"] if qtype == "yes_no" else [])
        counts = Counter(str(v) for v in values)
        # preserve declared option order, then any unexpected extras
        labels = list(options) + [k for k in counts if k not in options]
        data = [{"label": lab, "count": counts.get(lab, 0)} for lab in labels if lab]
        return {**base, "chart": "pie" if (qtype == "yes_no" or len(data) <= 6) else "bar", "data": data}

    if qtype == "multiple_choice":
        options = item.get("options") or []
        counts: Counter = Counter()
        for v in values:
            for sel in (v if isinstance(v, list) else [v]):
                counts[str(sel)] += 1
        labels = list(options) + [k for k in counts if k not in options]
        data = [{"label": lab, "count": counts.get(lab, 0)} for lab in labels if lab]
        return {**base, "chart": "bar", "data": data, "multi": True}

    if qtype in ("likert", "rating"):
        labels = item.get("scale_labels") or (["1", "2", "3", "4", "5"] if qtype == "rating" else _AGREE)
        nums = [int(x) for x in (_to_float(v) for v in values) if x is not None]
        counts = Counter(nums)
        data = [{"label": f"{i + 1}. {labels[i]}" if i < len(labels) else str(i + 1),
                 "count": counts.get(i + 1, 0)} for i in range(len(labels))]
        mean = round(statistics.mean(nums), 2) if nums else None
        return {**base, "chart": "likert", "data": data, "mean": mean, "scale_points": len(labels)}

    if qtype == "numeric":
        nums = [x for x in (_to_float(v) for v in values) if x is not None]
        stats = None
        if nums:
            stats = {
                "n": len(nums), "mean": round(statistics.mean(nums), 2),
                "median": round(statistics.median(nums), 2),
                "min": _fmt(min(nums)), "max": _fmt(max(nums)),
            }
        return {**base, "chart": "histogram", "data": _histogram(nums), "stats": stats}

    if qtype == "date":
        counts = Counter(str(v) for v in values)
        data = [{"label": k, "count": c} for k, c in sorted(counts.items())]
        return {**base, "chart": "bar", "data": data}

    # short_text / long_text → sampled responses, newest first
    samples = [str(v) for v in values if str(v).strip()][-10:][::-1]
    return {**base, "chart": "text", "samples": samples}


def build_analytics(structure: dict, responses: list[dict]) -> dict:
    """responses: list of answer dicts ({col_id: value})."""
    questions = []
    for s_idx, section in enumerate(structure.get("sections") or []):
        for i_idx, item in enumerate(section.get("items") or []):
            if not isinstance(item, dict):
                item = {"text": str(item), "type": "likert"}
            cid = _column_id(item, s_idx, i_idx)
            values = []
            for r in responses:
                v = r.get(cid)
                if v is None or v == "" or (isinstance(v, list) and not v):
                    continue
                values.append(v)
            item = {**item, "id": cid}
            questions.append(summarize_question(item, values))
    return {"response_count": len(responses), "questions": questions}
