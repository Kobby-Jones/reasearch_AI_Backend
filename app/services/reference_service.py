from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.bibtex import parse_bibtex
from app.ai.reference_client import lookup_doi, search_candidates
from app.ai.references import CitationLibrary, Reference, _make_key
from app.core.exceptions import NotFoundError, ValidationError
from app.models.reference import ProjectReference
from app.services.research_service import ResearchService


def _norm_title(t: str) -> str:
    return re.sub(r"\W+", "", (t or "").lower())[:60]


def _row_to_reference(row: ProjectReference) -> Reference:
    return Reference(
        key=row.citation_key,
        authors=list(row.authors or []),
        year=row.year,
        title=row.title,
        container=row.container,
        volume=row.volume,
        issue=row.issue,
        pages=row.pages,
        doi=row.doi,
        url=row.url,
        cited_by=row.cited_by or 0,
        abstract=row.abstract or "",
    )


def reference_to_payload(ref: Reference) -> dict:
    """Serialise a Reference (stored or candidate) with formatted previews."""
    return {
        "citation_key": ref.key,
        "authors": ref.authors,
        "year": ref.year,
        "title": ref.title,
        "container": ref.container,
        "volume": ref.volume,
        "issue": ref.issue,
        "pages": ref.pages,
        "doi": ref.doi,
        "url": ref.url,
        "abstract": ref.abstract,
        "cited_by": ref.cited_by,
        "apa": ref.apa(),
        "intext": ref.intext_parenthetical(),
    }


class ReferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.research = ResearchService(db)

    def _own_project(self, project_id: int, user_id: int):
        return self.research.get_owned(project_id, user_id)

    def list_for_project(self, user_id: int, project_id: int) -> list[ProjectReference]:
        self._own_project(project_id, user_id)
        return list(
            self.db.scalars(
                select(ProjectReference)
                .where(ProjectReference.project_id == project_id)
                .order_by(ProjectReference.id.desc())
            ).all()
        )

    def serialize(self, row: ProjectReference) -> dict:
        payload = reference_to_payload(_row_to_reference(row))
        payload.update({"id": row.id, "source": row.source, "created_at": row.created_at})
        return payload

    # ---- search (not persisted) ---------------------------------------------
    def search(self, user_id: int, project_id: int, query: str, limit: int = 12) -> list[dict]:
        self._own_project(project_id, user_id)
        if not query or not query.strip():
            raise ValidationError("Enter a search query.")
        return [reference_to_payload(r) for r in search_candidates(query, limit=limit)]

    # ---- add ------------------------------------------------------------------
    def _existing_keys(self, project_id: int) -> tuple[set[str], set[str], set[str]]:
        rows = self.db.scalars(
            select(ProjectReference).where(ProjectReference.project_id == project_id)
        ).all()
        keys = {r.citation_key for r in rows}
        dois = {(r.doi or "").lower() for r in rows if r.doi}
        titles = {_norm_title(r.title) for r in rows}
        return keys, dois, titles

    def _add_reference(self, project_id: int, user_id: int, ref: Reference, source: str) -> ProjectReference | None:
        keys, dois, titles = self._existing_keys(project_id)
        if ref.doi and ref.doi.lower() in dois:
            return None
        if _norm_title(ref.title) in titles:
            return None
        # ensure a unique citation key within the project
        if ref.key in keys:
            ref.key = _make_key(ref.authors, ref.year, set(keys))
        row = ProjectReference(
            project_id=project_id,
            user_id=user_id,
            citation_key=ref.key,
            authors=ref.authors,
            year=ref.year,
            title=ref.title,
            container=ref.container,
            volume=ref.volume,
            issue=ref.issue,
            pages=ref.pages,
            doi=ref.doi,
            url=ref.url,
            abstract=ref.abstract or "",
            cited_by=ref.cited_by or 0,
            source=source,
        )
        self.db.add(row)
        return row

    def add_manual(self, user_id: int, project_id: int, data: dict) -> ProjectReference:
        self._own_project(project_id, user_id)
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationError("A reference needs at least a title.")
        authors = data.get("authors") or []
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(";") if a.strip()]
        year = data.get("year")
        ref = Reference(
            key=data.get("citation_key") or _make_key(authors, year, set()),
            authors=authors, year=year, title=title,
            container=data.get("container"), volume=data.get("volume"),
            issue=data.get("issue"), pages=data.get("pages"),
            doi=(data.get("doi") or None), url=data.get("url"),
            cited_by=data.get("cited_by") or 0, abstract=data.get("abstract") or "",
        )
        row = self._add_reference(project_id, user_id, ref, data.get("source") or "manual")
        if row is None:
            raise ValidationError("That reference is already in this project's library.")
        self.db.commit()
        self.db.refresh(row)
        return row

    def add_doi(self, user_id: int, project_id: int, doi: str) -> ProjectReference:
        self._own_project(project_id, user_id)
        ref = lookup_doi(doi)
        if ref is None:
            raise NotFoundError("No work was found for that DOI.")
        row = self._add_reference(project_id, user_id, ref, "doi")
        if row is None:
            raise ValidationError("That reference is already in this project's library.")
        self.db.commit()
        self.db.refresh(row)
        return row

    def add_bibtex(self, user_id: int, project_id: int, text: str) -> list[ProjectReference]:
        self._own_project(project_id, user_id)
        parsed = parse_bibtex(text or "")
        if not parsed:
            raise ValidationError("No valid BibTeX entries were found.")
        added: list[ProjectReference] = []
        for ref in parsed:
            row = self._add_reference(project_id, user_id, ref, "bibtex")
            if row is not None:
                added.append(row)
        self.db.commit()
        for r in added:
            self.db.refresh(r)
        return added

    def delete(self, user_id: int, reference_id: int) -> None:
        row = self.db.get(ProjectReference, reference_id)
        if not row or row.user_id != user_id:
            raise NotFoundError("Reference not found.")
        self.db.delete(row)
        self.db.commit()

    # ---- integration: curated library for the report writer ------------------
    def library_for_project(self, project_id: int) -> CitationLibrary:
        rows = self.db.scalars(
            select(ProjectReference).where(ProjectReference.project_id == project_id)
        ).all()
        refs = {r.citation_key: _row_to_reference(r) for r in rows}
        return CitationLibrary(references=refs)
