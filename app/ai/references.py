"""Real, verifiable scholarly references.

This module retrieves genuine published works from open scholarly databases
(OpenAlex as primary, Crossref as fallback) and turns them into a *citation
library* that is the single source of truth for BOTH in-text citations and the
reference list. The report writer may only cite keys that exist in this library,
and the reference list is built from the same objects, so the two can never
drift apart and nothing is fabricated.

Design notes:
- Network access is injected (`fetch_json`) so the library is fully testable
  offline and so the caller controls timeouts / domains.
- If retrieval yields nothing (no network, API down), `build_library` returns an
  empty library. Callers must treat "no references" as "write without citations"
  rather than inventing any — fabricated references are worse than none.
- No API key is required for OpenAlex or Crossref.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

# A fetch_json callable takes (url, params) and returns parsed JSON or None.
FetchJson = Callable[[str, dict], Optional[dict]]

OPENALEX_WORKS = "https://api.openalex.org/works"
CROSSREF_WORKS = "https://api.crossref.org/works"


# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------
@dataclass
class Reference:
    key: str                      # stable in-text key, e.g. "Hilson2020"
    authors: list[str]            # ["Hilson, G.", "Potter, C."]
    year: Optional[int]
    title: str
    container: Optional[str] = None   # journal / book / publisher
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    cited_by: int = 0             # used only for ranking relevance/quality
    abstract: str = ""            # short snippet, when available (for synthesis)

    # ---- in-text forms ----
    def _surnames(self) -> list[str]:
        out = []
        for a in self.authors:
            surname = a.split(",")[0].strip() if "," in a else a.strip()
            if surname:
                out.append(surname)
        return out

    def intext_parenthetical(self) -> str:
        names = self._surnames()
        y = self.year or "n.d."
        if not names:
            # fall back to a short title
            short = self.title.split(":")[0][:40].strip()
            return f"(\u201c{short}\u201d, {y})"
        if len(names) == 1:
            who = names[0]
        elif len(names) == 2:
            who = f"{names[0]} & {names[1]}"
        else:
            who = f"{names[0]} et al."
        return f"({who}, {y})"

    def intext_narrative(self) -> str:
        names = self._surnames()
        y = self.year or "n.d."
        if not names:
            return self.intext_parenthetical()
        if len(names) == 1:
            who = names[0]
        elif len(names) == 2:
            who = f"{names[0]} and {names[1]}"
        else:
            who = f"{names[0]} et al."
        return f"{who} ({y})"

    # ---- reference-list form (APA 7) ----
    def apa(self) -> str:
        author_str = self._apa_authors()
        y = f"({self.year})." if self.year else "(n.d.)."
        title = self.title.rstrip(".")
        parts = [p for p in [author_str, y] if p]
        # italics can't be represented in plain text; the docx builder applies it.
        if self.container:
            src = self.container.rstrip(".")
            vol = ""
            if self.volume:
                vol = f", {self.volume}"
                if self.issue:
                    vol += f"({self.issue})"
            pages = f", {self.pages}" if self.pages else ""
            parts.append(f"{title}. {src}{vol}{pages}.")
        else:
            parts.append(f"{title}.")
        ref = " ".join(parts)
        if self.doi:
            ref += f" https://doi.org/{self.doi}"
        elif self.url:
            ref += f" {self.url}"
        return re.sub(r"\s+", " ", ref).strip()

    def _apa_authors(self) -> str:
        names = self.authors
        if not names:
            return ""
        if len(names) > 20:
            names = names[:19] + ["... " + names[-1]]
        if len(names) == 1:
            return f"{names[0]}"
        return ", ".join(names[:-1]) + f", & {names[-1]}"


@dataclass
class CitationLibrary:
    references: dict[str, Reference] = field(default_factory=dict)
    _used: set[str] = field(default_factory=set)

    def __bool__(self) -> bool:
        return bool(self.references)

    def keys(self) -> list[str]:
        return list(self.references.keys())

    def mark_used(self, key: str) -> bool:
        if key in self.references:
            self._used.add(key)
            return True
        return False

    def catalog_for_prompt(self, limit: int = 40) -> str:
        """Compact catalog the writer sees: key + who/year/title/venue."""
        lines = []
        for ref in list(self.references.values())[:limit]:
            who = "; ".join(ref._surnames()) or "Unknown"
            venue = f" — {ref.container}" if ref.container else ""
            lines.append(f"[[{ref.key}]] {who} ({ref.year or 'n.d.'}). {ref.title}{venue}")
        return "\n".join(lines)

    def reference_list(self, used_only: bool = True) -> list[str]:
        refs = [
            r for k, r in self.references.items()
            if (not used_only) or k in self._used
        ]
        refs.sort(key=lambda r: (r._surnames()[0].lower() if r._surnames() else r.title.lower(),
                                 r.year or 0))
        return [r.apa() for r in refs]


# ---------------------------------------------------------------------------
# key generation
# ---------------------------------------------------------------------------
def _ascii(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _make_key(authors: list[str], year: Optional[int], taken: set[str]) -> str:
    if authors:
        first = authors[0].split(",")[0].strip()
    else:
        first = "Anon"
    base = re.sub(r"[^A-Za-z]", "", _ascii(first)) or "Anon"
    base = base[:18] + (str(year) if year else "nd")
    key = base
    suffix = ord("a")
    while key in taken:
        key = base + chr(suffix)
        suffix += 1
    taken.add(key)
    return key


# ---------------------------------------------------------------------------
# providers: normalise each API's payload into Reference objects
# ---------------------------------------------------------------------------
def _name_from_openalex(authorship: dict) -> Optional[str]:
    disp = (authorship.get("author") or {}).get("display_name")
    if not disp:
        return None
    parts = disp.strip().split()
    if len(parts) == 1:
        return parts[0]
    surname = parts[-1]
    initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
    return f"{surname}, {initials}"


def _parse_openalex(data: dict, taken: set[str]) -> list[Reference]:
    out: list[Reference] = []
    for w in (data or {}).get("results", []):
        title = (w.get("title") or "").strip()
        if not title:
            continue
        authors = [n for a in (w.get("authorships") or []) if (n := _name_from_openalex(a))]
        year = w.get("publication_year")
        loc = (w.get("primary_location") or {}).get("source") or {}
        container = loc.get("display_name")
        biblio = w.get("biblio") or {}
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        key = _make_key(authors, year, taken)
        out.append(Reference(
            key=key, authors=authors, year=year, title=title, container=container,
            volume=biblio.get("volume"), issue=biblio.get("issue"),
            pages=_pages(biblio.get("first_page"), biblio.get("last_page")),
            doi=doi, url=w.get("id"), cited_by=w.get("cited_by_count") or 0,
            abstract=_openalex_abstract(w.get("abstract_inverted_index")),
        ))
    return out


def _openalex_abstract(inverted: dict | None, max_words: int = 80) -> str:
    """Reconstruct an abstract snippet from OpenAlex's inverted index."""
    if not isinstance(inverted, dict) or not inverted:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    words = [w for _, w in positions[:max_words]]
    return " ".join(words)


def _name_from_crossref(author: dict) -> Optional[str]:
    family = author.get("family")
    given = author.get("given")
    if not family:
        return None
    if given:
        initials = " ".join(f"{p[0]}." for p in given.replace(".", " ").split() if p)
        return f"{family}, {initials}"
    return family


def _parse_crossref(data: dict, taken: set[str]) -> list[Reference]:
    out: list[Reference] = []
    items = ((data or {}).get("message") or {}).get("items", [])
    for w in items:
        title_list = w.get("title") or []
        title = (title_list[0] if title_list else "").strip()
        if not title:
            continue
        authors = [n for a in (w.get("author") or []) if (n := _name_from_crossref(a))]
        year = None
        for k in ("published-print", "published-online", "issued", "created"):
            dp = (w.get(k) or {}).get("date-parts") or []
            if dp and dp[0] and dp[0][0]:
                year = dp[0][0]
                break
        container = (w.get("container-title") or [None])[0]
        key = _make_key(authors, year, taken)
        out.append(Reference(
            key=key, authors=authors, year=year, title=title, container=container,
            volume=w.get("volume"), issue=w.get("issue"), pages=w.get("page"),
            doi=w.get("DOI"), url=w.get("URL"),
            cited_by=w.get("is-referenced-by-count") or 0,
        ))
    return out


def _pages(first, last) -> Optional[str]:
    if first and last:
        return f"{first}-{last}"
    return first or None


# ---------------------------------------------------------------------------
# retrieval orchestration
# ---------------------------------------------------------------------------
def _queries(topic: str, field_: Optional[str], constructs: Iterable[str]) -> list[str]:
    qs: list[str] = []
    if topic:
        qs.append(topic)
    cons = [c for c in (constructs or []) if c]
    # pair the two most salient constructs with the field for focused hits
    if cons and field_:
        qs.append(f"{cons[0]} {field_}")
    for c in cons[:4]:
        qs.append(f"{c} {topic.split()[0] if topic else ''}".strip())
    # dedupe, keep order
    seen, out = set(), []
    for q in qs:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out[:6]


def build_library(
    topic: str,
    field_: Optional[str],
    constructs: Iterable[str],
    *,
    fetch_json: FetchJson,
    max_refs: int = 40,
    per_query: int = 8,
    mailto: str = "support@researchai.app",
) -> CitationLibrary:
    """Retrieve real works for the project and assemble a citation library.

    Never raises on network problems: a failed fetch yields fewer (or zero)
    references, and the caller writes with whatever is available.
    """
    taken: set[str] = set()
    by_doi: dict[str, Reference] = {}
    by_title: dict[str, Reference] = {}

    def add(ref: Reference) -> None:
        if ref.doi:
            dkey = ref.doi.lower()
            if dkey in by_doi:
                return
            by_doi[dkey] = ref
        tkey = re.sub(r"\W+", "", ref.title.lower())[:60]
        if tkey in by_title:
            return
        by_title[tkey] = ref

    for q in _queries(topic, field_, constructs):
        # --- OpenAlex (primary) ---
        oa = _safe(fetch_json, OPENALEX_WORKS, {
            "search": q,
            "per-page": per_query,
            "sort": "relevance_score:desc",
            "filter": "has_abstract:true,type:article",
            "mailto": mailto,
        })
        refs = _parse_openalex(oa, taken) if oa else []
        # --- Crossref (fallback if OpenAlex gave little) ---
        if len(refs) < 3:
            cr = _safe(fetch_json, CROSSREF_WORKS, {
                "query": q, "rows": per_query, "select":
                "DOI,title,author,container-title,volume,issue,page,issued,URL,is-referenced-by-count",
                "mailto": mailto,
            })
            refs += _parse_crossref(cr, taken) if cr else []
        for r in refs:
            add(r)

    # rank by citation count (a rough quality/seminality signal), keep max_refs
    ranked = sorted(by_title.values(), key=lambda r: r.cited_by, reverse=True)[:max_refs]
    return CitationLibrary(references={r.key: r for r in ranked})


def _safe(fetch_json: FetchJson, url: str, params: dict) -> Optional[dict]:
    try:
        return fetch_json(url, params)
    except Exception:
        return None
