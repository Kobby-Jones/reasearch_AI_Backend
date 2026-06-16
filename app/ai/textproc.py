"""Post-process generated prose so it cites only real, retrieved sources and
contains no em-dashes.

The writer is instructed to mark citations as ``[[Key]]`` (parenthetical) or
``[[Key|narrative]]`` (e.g. "Hilson and Maconachie (2020) argue..."). Here we:

1. Replace each marker with the correct in-text form from the citation library.
2. Record which keys were actually used (so the reference list lists only those).
3. Delete any marker whose key is NOT in the library — the model is forbidden
   from inventing sources, and this is the safety net that enforces it.
4. Remove em-dashes (and spaced en-dashes used as punctuation), leaving genuine
   numeric ranges like "125-141" untouched.
"""
from __future__ import annotations

import re

from app.ai.references import CitationLibrary

_MARKER = re.compile(r"\[\[\s*([A-Za-z][A-Za-z0-9]*)\s*(\|\s*narrative\s*)?\]\]")


def apply_citations(text: str, library: CitationLibrary | None) -> str:
    if not text:
        return text

    def repl(m: re.Match) -> str:
        key = m.group(1)
        narrative = bool(m.group(2))
        if library is None or key not in library.references:
            return ""  # unknown/invented key -> removed entirely
        library.mark_used(key)
        ref = library.references[key]
        return ref.intext_narrative() if narrative else ref.intext_parenthetical()

    out = _MARKER.sub(repl, text)
    out = _tidy_after_removal(out)
    return strip_em_dashes(out)


def _tidy_after_removal(text: str) -> str:
    # collapse artefacts left by removed markers, e.g. " ()", " (, )", doubled spaces
    text = re.sub(r"\(\s*[;,]\s*", "(", text)
    text = re.sub(r"\s*[;,]\s*\)", ")", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    return text


def strip_em_dashes(text: str) -> str:
    """Replace em-dashes (and spaced en-dashes used as punctuation) with commas,
    while preserving en-dashes inside numeric ranges (e.g. 2014-2024, 125-141)."""
    if not text:
        return text
    # protect numeric ranges using en/em dash: 2014–2024 -> 2014-2024
    text = re.sub(r"(?<=\d)\s*[\u2013\u2014]\s*(?=\d)", "-", text)
    # em-dash as punctuation: "word — word" or "word—word" -> "word, word"
    text = re.sub(r"\s*\u2014\s*", ", ", text)
    # spaced en-dash as punctuation -> comma; keep unspaced en-dash (rare) as hyphen
    text = re.sub(r"\s+\u2013\s+", ", ", text)
    text = text.replace("\u2013", "-")
    # clean any ", ," or ",," doubles and space-before-punctuation introduced above
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def finalize_prose(text: str, library: CitationLibrary | None) -> str:
    """Convenience: resolve citations then strip em-dashes."""
    return apply_citations(text, library)
