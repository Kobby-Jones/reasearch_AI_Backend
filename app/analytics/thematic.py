"""Thematic analysis for qualitative (free-text) data.

Division of labour, by design:

- The AI *induces themes* from the student's real responses and *codes* each
  response (which themes apply, plus a supporting span). Deriving themes from
  text the student actually wrote is legitimate qualitative analysis.
- Python does all the *counting* (theme frequency, prevalence, co-occurrence)
  and *verifies every quote is verbatim* from a real response. Anything the AI
  returns that is not found in the source text is discarded. This is the
  anti-fabrication guarantee: no invented quotes, no invented numbers.

The coder is injected (``ThematicCoder``) so the engine is fully testable
offline; the default implementation calls the AI client.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Protocol


class ThematicCoder(Protocol):
    def induce_themes(self, responses: list[str]) -> list[dict]:
        """Return [{'name','definition'}] induced from a sample of responses."""
        ...

    def code_responses(self, responses: list[str], themes: list[dict]) -> list[dict]:
        """Return per-response [{'themes':[name,...], 'quote': 'verbatim span'}]."""
        ...


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _verbatim(quote: str, source: str, max_words: int = 30) -> str | None:
    """Return a cleaned quote only if it genuinely appears in the source."""
    if not quote:
        return None
    q = _norm(quote)
    src = _norm(source)
    if len(q) < 4 or q not in src:
        return None
    # trim to max_words, preserving original casing from the source slice
    start = src.find(q)
    # map back to original source by length proportion (best-effort, safe)
    words = quote.strip().split()
    trimmed = " ".join(words[:max_words])
    return trimmed.rstrip(" ,.;:") if trimmed else None


def run_thematic(
    responses: list[str],
    coder: ThematicCoder,
    *,
    max_quotes_per_theme: int = 3,
    induce_sample: int = 60,
) -> dict:
    clean = [r.strip() for r in responses if isinstance(r, str) and r.strip()]
    if len(clean) < 3:
        raise ValueError("Thematic analysis needs at least three non-empty text responses.")

    themes = coder.induce_themes(clean[:induce_sample]) or []
    theme_names = [t["name"] for t in themes if t.get("name")]
    if not theme_names:
        raise ValueError("No themes could be induced from the responses.")

    coded = coder.code_responses(clean, themes)

    # --- Python does the counting ---
    theme_count: dict[str, int] = defaultdict(int)
    theme_quotes: dict[str, list[str]] = defaultdict(list)
    cooccur: dict[tuple[str, str], int] = defaultdict(int)
    coded_n = 0

    for resp, c in zip(clean, coded):
        applied = [t for t in (c.get("themes") or []) if t in theme_names]
        applied = list(dict.fromkeys(applied))  # dedupe, keep order
        if applied:
            coded_n += 1
        for t in applied:
            theme_count[t] += 1
            # verify the supporting quote is verbatim from THIS response
            if len(theme_quotes[t]) < max_quotes_per_theme:
                q = _verbatim(c.get("quote", ""), resp)
                if q and q not in theme_quotes[t]:
                    theme_quotes[t].append(q)
        for i in range(len(applied)):
            for j in range(i + 1, len(applied)):
                a, b = sorted((applied[i], applied[j]))
                cooccur[(a, b)] += 1

    n = len(clean)
    theme_rows = []
    for t in themes:
        name = t.get("name")
        if not name:
            continue
        freq = theme_count.get(name, 0)
        theme_rows.append({
            "name": name,
            "definition": t.get("definition", ""),
            "frequency": freq,
            "prevalence": round(freq / n, 4) if n else 0.0,
            "quotes": theme_quotes.get(name, []),
        })
    theme_rows.sort(key=lambda r: r["frequency"], reverse=True)

    return {
        "method": "thematic",
        "n_responses": n,
        "n_coded": coded_n,
        "n_themes": len(theme_rows),
        "themes": theme_rows,
        "cooccurrence": [
            {"a": a, "b": b, "count": cnt}
            for (a, b), cnt in sorted(cooccur.items(), key=lambda x: x[1], reverse=True)
        ],
    }
