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
