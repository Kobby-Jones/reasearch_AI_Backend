"""Literature synthesis for review / conceptual studies.

Takes the REAL sources retrieved by the citation engine and organises them into
themes and research gaps. As everywhere else, the AI does the *organising* but
may not invent: every source a theme cites is verified to exist in the library,
and the rendered citations come from the library, so nothing is fabricated.

The synthesizer is injected for offline testing; the default calls the AI client.
"""
from __future__ import annotations

from typing import Protocol

from app.ai.references import CitationLibrary


class Synthesizer(Protocol):
    def synthesize(self, catalog: str, topic: str, field: str | None) -> dict:
        """Return {'themes':[{'name','synthesis','sources':[key,...]}], 'gaps':[...]}"""
        ...


def build_synthesis(
    library: CitationLibrary,
    topic: str,
    field: str | None,
    synthesizer: Synthesizer,
    *,
    max_sources_per_theme: int = 8,
) -> dict:
    if not library:
        raise ValueError("No sources were retrieved, so a synthesis cannot be built.")

    catalog = library.catalog_for_prompt(limit=40)
    raw = synthesizer.synthesize(catalog, topic, field) or {}

    valid_keys = set(library.references.keys())
    themes_out = []
    for t in (raw.get("themes") or []):
        name = (t.get("name") or "").strip()
        if not name:
            continue
        # keep only real, retrieved sources
        keys = [k for k in (t.get("sources") or []) if k in valid_keys][:max_sources_per_theme]
        for k in keys:
            library.mark_used(k)
        sources = [{
            "key": k,
            "citation": library.references[k].intext_parenthetical(),
            "apa": library.references[k].apa(),
        } for k in keys]
        themes_out.append({
            "name": name,
            "synthesis": (t.get("synthesis") or "").strip(),
            "n_sources": len(sources),
            "sources": sources,
        })

    gaps = [g.strip() for g in (raw.get("gaps") or []) if isinstance(g, str) and g.strip()]

    return {
        "method": "synthesis",
        "topic": topic,
        "n_sources": len(library.references),
        "n_themes": len(themes_out),
        "themes": themes_out,
        "gaps": gaps,
        "references": library.reference_list(used_only=True),
    }
