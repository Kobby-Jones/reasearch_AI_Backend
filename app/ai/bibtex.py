"""A small, dependency-free BibTeX parser.

Good enough for the common entry types researchers paste from Google Scholar,
Zotero, or Mendeley. Tolerant of messy input: unknown fields are ignored and a
malformed entry is skipped rather than raising.
"""
from __future__ import annotations

import re

from app.ai.references import Reference, _make_key


def _read_value(s: str, i: int) -> tuple[str, int]:
    """Read a field value starting at i; supports {..} (balanced), "..", or bare."""
    n = len(s)
    while i < n and s[i] in " \t\r\n":
        i += 1
    if i >= n:
        return "", i
    ch = s[i]
    if ch == "{":
        depth, j = 0, i
        while j < n:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1 : j], j + 1
            j += 1
        return s[i + 1 :], n
    if ch == '"':
        j = i + 1
        while j < n and s[j] != '"':
            j += 1
        return s[i + 1 : j], j + 1
    # bare value up to comma or closing brace
    j = i
    while j < n and s[j] not in ",}\n":
        j += 1
    return s[i:j].strip(), j


def _clean(v: str) -> str:
    v = v.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", v).strip()


def _authors(raw: str) -> list[str]:
    if not raw:
        return []
    out = []
    for part in re.split(r"\s+and\s+", _clean(raw)):
        part = part.strip()
        if not part:
            continue
        if "," in part:  # already "Surname, Given"
            family, _, given = part.partition(",")
            initials = " ".join(f"{p[0]}." for p in given.split() if p)
            out.append(f"{family.strip()}, {initials}".strip().rstrip(","))
        else:  # "Given Surname"
            toks = part.split()
            if len(toks) == 1:
                out.append(toks[0])
            else:
                family = toks[-1]
                initials = " ".join(f"{p[0]}." for p in toks[:-1])
                out.append(f"{family}, {initials}")
    return out


def parse_bibtex(text: str) -> list[Reference]:
    refs: list[Reference] = []
    taken: set[str] = set()
    # iterate entries by '@type{...'
    for m in re.finditer(r"@\s*\w+\s*\{", text):
        start = m.end()
        # capture the entry body up to the matching closing brace
        depth, j, n = 1, start, len(text)
        while j < n and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[start : j - 1]
        # drop the citekey (up to first comma)
        _, _, fields_str = body.partition(",")

        fields: dict[str, str] = {}
        i = 0
        for fm in re.finditer(r"(\w+)\s*=\s*", fields_str):
            name = fm.group(1).lower()
            val, _ = _read_value(fields_str, fm.end())
            fields[name] = _clean(val)

        title = fields.get("title", "").strip()
        if not title:
            continue
        authors = _authors(fields.get("author", ""))
        year = None
        if fields.get("year", "").isdigit():
            year = int(fields["year"])
        container = fields.get("journal") or fields.get("booktitle") or fields.get("publisher")
        ref = Reference(
            key=_make_key(authors, year, taken),
            authors=authors,
            year=year,
            title=title,
            container=container,
            volume=fields.get("volume"),
            issue=fields.get("number") or fields.get("issue"),
            pages=(fields.get("pages") or "").replace("--", "-") or None,
            doi=(fields.get("doi") or "").replace("https://doi.org/", "") or None,
            url=fields.get("url"),
        )
        refs.append(ref)
    return refs
