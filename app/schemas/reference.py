from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReferenceOut(BaseModel):
    id: int
    citation_key: str
    authors: list[str] = []
    year: int | None = None
    title: str
    container: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    cited_by: int = 0
    source: str
    apa: str
    intext: str
    created_at: datetime


class ReferenceCandidate(BaseModel):
    citation_key: str
    authors: list[str] = []
    year: int | None = None
    title: str
    container: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    cited_by: int = 0
    apa: str
    intext: str


class ReferenceSearchRequest(BaseModel):
    project_id: int
    query: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=12, ge=1, le=25)


class ReferenceAddRequest(BaseModel):
    project_id: int
    # any subset of reference fields; title is required by the service
    title: str | None = None
    citation_key: str | None = None
    authors: list[str] | str | None = None
    year: int | None = None
    container: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    cited_by: int | None = None
    source: str | None = None


class ReferenceDoiRequest(BaseModel):
    project_id: int
    doi: str = Field(min_length=3, max_length=255)


class ReferenceBibtexRequest(BaseModel):
    project_id: int
    bibtex: str = Field(min_length=5)
