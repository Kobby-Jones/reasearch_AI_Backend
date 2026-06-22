"""Live HTTP wiring for scholarly reference retrieval.

Kept separate from ``app.ai.references`` so that module stays pure and unit-
testable. This is where real network access happens (OpenAlex / Crossref), using
the same ``httpx`` dependency already used by the payment service.
"""
from __future__ import annotations

from typing import Optional

import httpx

from app.ai.references import CitationLibrary, build_library
from app.core.config import settings


def _httpx_fetch_json(url: str, params: dict) -> Optional[dict]:
    try:
        resp = httpx.get(
            url, params=params, timeout=getattr(settings, "reference_timeout", 15),
            headers={"User-Agent": f"ResearchAI/1.0 (mailto:{_mailto()})"},
        )
    except httpx.HTTPError:
        return None
    if resp.status_code >= 400:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _mailto() -> str:
    return getattr(settings, "reference_mailto", "support@researchai.app")


def build_project_library(
    topic: str,
    field_: Optional[str],
    constructs: list[str],
    *,
    max_refs: int | None = None,
) -> CitationLibrary:
    """Retrieve a real citation library for a project.

    Returns an empty library (never raises) if reference retrieval is disabled or
    the network is unavailable; callers then write without citations rather than
    inventing any.
    """
    if not getattr(settings, "references_enabled", True):
        return CitationLibrary()
    return build_library(
        topic, field_, constructs,
        fetch_json=_httpx_fetch_json,
        max_refs=max_refs or getattr(settings, "reference_max", 40),
        mailto=_mailto(),
    )


def search_candidates(query: str, *, limit: int = 12):
    """Search scholarly databases for a free-text query; returns Reference objects.

    Reuses the same retrieval/normalisation as the report writer, so curated
    references are identical in shape to auto-retrieved ones.
    """
    if not query or not query.strip():
        return []
    lib = build_library(
        query.strip(), None, [],
        fetch_json=_httpx_fetch_json,
        max_refs=limit,
        per_query=limit,
        mailto=_mailto(),
    )
    return list(lib.references.values())


def lookup_doi(doi: str):
    """Resolve a single DOI via Crossref into a Reference, or None."""
    from app.ai.references import _parse_crossref  # local import to avoid cycle

    doi = (doi or "").strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
    if not doi:
        return None
    data = _httpx_fetch_json(f"https://api.crossref.org/works/{doi}", {"mailto": _mailto()})
    if not data or "message" not in data:
        return None
    # /works/{doi} returns the item directly under "message"; adapt to the
    # list shape _parse_crossref expects.
    wrapped = {"message": {"items": [data["message"]]}}
    refs = _parse_crossref(wrapped, set())
    return refs[0] if refs else None
