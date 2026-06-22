"""Deterministic question-type inference for survey instruments.

The AI (or a weak prompt) tends to emit every item as a 5-point Likert row, even
for demographics and free-text questions. This module repairs that: given a
question's wording, it picks an appropriate input type and, where it can,
synthesises sensible answer options. It is pure and deterministic, so the
instrument is correct regardless of model quality, and existing instruments can
be upgraded in place.

Supported types:
  single_choice, multiple_choice, dropdown, likert, rating, yes_no,
  short_text, long_text, numeric, date
"""
from __future__ import annotations

import re

QUESTION_TYPES = {
    "single_choice", "multiple_choice", "dropdown", "likert", "rating",
    "yes_no", "short_text", "long_text", "numeric", "date",
}

LIKERT_AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
LIKERT_FREQ = ["Never", "Rarely", "Sometimes", "Often", "Always"]

# Canonical demographic option sets.
_AGE_BANDS = ["Under 18", "18–24", "25–34", "35–44", "45–54", "55–64", "65 or older"]
_GENDER = ["Male", "Female", "Non-binary", "Prefer not to say"]
_EDU = ["Undergraduate", "Postgraduate – Master's", "Postgraduate – PhD",
        "Diploma / Certificate", "Other"]
_YEAR = ["Year 1", "Year 2", "Year 3", "Year 4", "Postgraduate"]
_MARITAL = ["Single", "Married", "Divorced", "Widowed", "Prefer not to say"]
_EMPLOY = ["Employed full-time", "Employed part-time", "Self-employed",
           "Unemployed", "Student", "Retired"]
_RELIGION = ["Christianity", "Islam", "Traditional", "None", "Other"]


def _kw(text: str, *words: str) -> bool:
    return any(w in text for w in words)


def infer_type(text: str, existing_type: str | None = None, has_options: bool = False) -> dict:
    """Return {type, options?, scale_labels?} for a question, by its wording.

    A genuine attitudinal Likert item is preserved; a demographic or factual
    item mistakenly typed as Likert is repaired.
    """
    t = (text or "").strip().lower()

    # ---- known demographics (highest priority) ------------------------------
    if _kw(t, "age") and not _kw(t, "manage", "page", "usage", "average"):
        if _kw(t, "exact age", "in years", "your age in"):
            return {"type": "numeric"}
        return {"type": "single_choice", "options": list(_AGE_BANDS)}
    if _kw(t, "gender", "sex "):
        return {"type": "single_choice", "options": list(_GENDER), "allow_other": True}
    if _kw(t, "marital"):
        return {"type": "single_choice", "options": list(_MARITAL)}
    if _kw(t, "year of study", "current year", "year of program", "academic year"):
        return {"type": "single_choice", "options": list(_YEAR)}
    if _kw(t, "level of study", "level of education", "highest level", "highest qualification",
           "educational level", "education level") or (_kw(t, "education") and _kw(t, "level")):
        return {"type": "single_choice", "options": list(_EDU)}
    if _kw(t, "employment status", "employment"):
        return {"type": "single_choice", "options": list(_EMPLOY)}
    if _kw(t, "religion", "religious affiliation"):
        return {"type": "single_choice", "options": list(_RELIGION), "allow_other": True}

    # free-text demographics that vary too widely to enumerate.
    # Unambiguous identity nouns match anywhere:
    if _kw(t, "field of study", "discipline", "programme of study", "program of study",
           "major", "occupation", "profession", "job title", "nationality",
           "country of origin", "country do you", "your country"):
        return {"type": "short_text"}
    # Generic nouns (which also appear in attitudinal items) only count as
    # demographics when framed possessively or as a name:
    for noun in ("department", "institution", "organisation", "organization",
                 "university", "region", "district", "city", "town", "company"):
        if _kw(t, f"your {noun}", f"which {noun}", f"name of {noun}", f"{noun} name",
               f"what {noun}"):
            return {"type": "short_text"}

    # ---- explicit cues ------------------------------------------------------
    if _kw(t, "please specify", "(please specify", "specify the name", "state the name",
           "(name)", "kindly specify"):
        return {"type": "short_text"}
    if _kw(t, "select all", "tick all", "check all", "choose all", "mark all",
           "all that apply", "that apply"):
        # only a real multi-select if options accompany it; else fall back
        return {"type": "multiple_choice"} if has_options else {"type": "short_text"}
    if _kw(t, "date of", "what date", "on what date", "date when", "day you"):
        return {"type": "date"}
    if _kw(t, "how would you rate", "rate the", "rate your", "give a rating", "rating of",
           "on a scale of 1", "score out of"):
        return {"type": "rating", "scale_labels": ["1", "2", "3", "4", "5"]}

    # counts / quantities → numeric
    if _kw(t, "how many", "number of", "how much", "how many times", "count of",
           "what is your age in"):
        return {"type": "numeric"}

    # frequency attitudinal → Likert (frequency labels)
    if _kw(t, "how often", "how frequently", "how regularly"):
        return {"type": "likert", "scale_labels": list(LIKERT_FREQ)}

    # open-ended reflection → long text
    if _kw(t, "describe", "explain", "elaborate", "in your opinion", "why do", "why are",
           "what challenges", "what factors", "suggest", "recommend", "comment on",
           "your thoughts", "how would you describe", "what are your views", "share your"):
        return {"type": "long_text"}

    # yes/no phrasing (short, closed)
    if re.match(r"^(do|does|did|have|has|are|is|was|were|can|could|would|will|should)\b", t) \
            and len(t.split()) <= 14 and not _kw(t, "how", "what", "which", "to what extent"):
        return {"type": "yes_no"}

    # attitudinal scale cues → Likert (agreement)
    if _kw(t, "to what extent", "how satisfied", "how likely", "how important",
           "how confident", "how comfortable", "agree", "satisfaction", "i believe",
           "i think", "i feel", "in my view"):
        return {"type": "likert", "scale_labels": list(LIKERT_AGREE)}

    # ---- preserve sensible existing typing ----------------------------------
    mapped = {"categorical": "single_choice", "choice": "single_choice",
              "text": "short_text", "open": "long_text", "number": "numeric",
              "integer": "numeric", "float": "numeric"}.get(existing_type or "", existing_type)
    if mapped in QUESTION_TYPES:
        if mapped == "single_choice" and not has_options:
            pass  # a choice with no options is useless; fall through
        else:
            return {"type": mapped}

    # ---- final fallbacks ----------------------------------------------------
    # A declarative statement (no question mark) reads as a Likert item; an
    # actual question with no other signal becomes a short text answer.
    if "?" not in t and len(t.split()) >= 4:
        return {"type": "likert", "scale_labels": list(LIKERT_AGREE)}
    return {"type": "short_text"}


def normalize_item(item: dict) -> dict:
    if not isinstance(item, dict):
        item = {"text": str(item)}
    text = item.get("text") or ""
    existing = item.get("type")
    options = item.get("options") or []
    has_options = isinstance(options, list) and len(options) >= 2

    inferred = infer_type(text, existing, has_options)
    out = dict(item)
    out["type"] = inferred["type"]

    # options: keep author-provided ones for choice types; else use synthesised
    if out["type"] in ("single_choice", "multiple_choice", "dropdown"):
        out["options"] = options if has_options else inferred.get("options", [])
        # promote long option lists to a dropdown for usability
        if out["type"] == "single_choice" and len(out["options"]) > 7:
            out["type"] = "dropdown"
    else:
        out.pop("options", None)

    if out["type"] in ("likert", "rating"):
        out["scale_labels"] = item.get("scale_labels") or inferred.get("scale_labels") or list(LIKERT_AGREE)
    else:
        out.pop("scale_labels", None)

    if "allow_other" in inferred and out["type"] in ("single_choice", "multiple_choice", "dropdown"):
        out.setdefault("allow_other", inferred["allow_other"])

    out.setdefault("required", True)
    return out


def normalize_structure(structure: dict) -> dict:
    """Return the structure with every item assigned a proper type/options."""
    if not isinstance(structure, dict):
        return structure
    out = dict(structure)
    sections = []
    for section in structure.get("sections", []) or []:
        s = dict(section)
        s["items"] = [normalize_item(it) for it in (section.get("items") or [])]
        sections.append(s)
    out["sections"] = sections
    return out


_CHOICE = ("single_choice", "multiple_choice", "dropdown")


def sanitize_item(item: dict, fallback_id: str) -> dict:
    """Ensure an author-edited item is structurally valid WITHOUT changing the
    type/options the author deliberately chose. Used when saving manual edits."""
    if not isinstance(item, dict):
        item = {"text": str(item)}
    out: dict = {}
    out["id"] = str(item.get("id") or fallback_id)
    out["text"] = (item.get("text") or "").strip()
    t = item.get("type")
    out["type"] = t if t in QUESTION_TYPES else "short_text"
    out["required"] = bool(item.get("required", True))

    if out["type"] in _CHOICE:
        opts = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
        out["options"] = opts or ["Option 1", "Option 2"]
        if item.get("allow_other"):
            out["allow_other"] = True
    if out["type"] in ("likert", "rating"):
        labels = [str(x) for x in (item.get("scale_labels") or []) if str(x).strip()]
        out["scale_labels"] = labels or list(LIKERT_AGREE)
    return out


def sanitize_structure(structure: dict) -> dict:
    """Validate/repair an author-edited structure for safe persistence."""
    if not isinstance(structure, dict):
        raise ValueError("Invalid questionnaire structure.")
    out = dict(structure)
    sections = []
    for s_idx, section in enumerate(structure.get("sections", []) or []):
        sec = dict(section)
        sec["id"] = str(section.get("id") or chr(65 + s_idx))
        sec["title"] = (section.get("title") or f"Section {sec['id']}").strip()
        items = []
        for i_idx, it in enumerate(section.get("items") or []):
            si = sanitize_item(it, f"{sec['id'].lower()}{i_idx + 1}")
            if si["text"]:  # drop blank questions
                items.append(si)
        sec["items"] = items
        sections.append(sec)
    out["sections"] = [s for s in sections if s["items"] or True]
    return out
