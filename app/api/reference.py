from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.reference import (
    ReferenceAddRequest,
    ReferenceBibtexRequest,
    ReferenceCandidate,
    ReferenceDoiRequest,
    ReferenceOut,
    ReferenceSearchRequest,
)
from app.services.reference_service import ReferenceService

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("", response_model=list[ReferenceOut])
def list_references(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReferenceOut]:
    svc = ReferenceService(db)
    return [ReferenceOut(**svc.serialize(r)) for r in svc.list_for_project(user.id, project_id)]


@router.post("/search", response_model=list[ReferenceCandidate])
def search_references(
    payload: ReferenceSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReferenceCandidate]:
    svc = ReferenceService(db)
    return [ReferenceCandidate(**c) for c in svc.search(user.id, payload.project_id, payload.query, payload.limit)]


@router.post("", response_model=ReferenceOut, status_code=201)
def add_reference(
    payload: ReferenceAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReferenceOut:
    svc = ReferenceService(db)
    data = payload.model_dump(exclude={"project_id"}, exclude_none=True)
    row = svc.add_manual(user.id, payload.project_id, data)
    return ReferenceOut(**svc.serialize(row))


@router.post("/doi", response_model=ReferenceOut, status_code=201)
def add_by_doi(
    payload: ReferenceDoiRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReferenceOut:
    svc = ReferenceService(db)
    row = svc.add_doi(user.id, payload.project_id, payload.doi)
    return ReferenceOut(**svc.serialize(row))


@router.post("/bibtex", response_model=list[ReferenceOut], status_code=201)
def add_by_bibtex(
    payload: ReferenceBibtexRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReferenceOut]:
    svc = ReferenceService(db)
    rows = svc.add_bibtex(user.id, payload.project_id, payload.bibtex)
    return [ReferenceOut(**svc.serialize(r)) for r in rows]


@router.delete("/{reference_id}", status_code=204, response_class=Response)
def delete_reference(
    reference_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    ReferenceService(db).delete(user.id, reference_id)
    return Response(status_code=204)
