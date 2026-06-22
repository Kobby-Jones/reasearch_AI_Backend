from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.research import ResearchProjectOut, TopicRequest
from app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/topic", response_model=ResearchProjectOut, status_code=201)
def create_topic(
    payload: TopicRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchProjectOut:
    project = ResearchService(db).create_from_topic(user.id, payload.topic, payload.field)
    from app.services.audit_service import audit
    audit(db, user.id, "project.create", target_type="project", target_id=project.id,
          summary=f"Created project: {project.topic[:80]}")
    return ResearchProjectOut.model_validate(project)


@router.post("/sample", response_model=ResearchProjectOut, status_code=201)
def create_sample(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchProjectOut:
    """Seed (or return) a complete demo project so new users can explore the
    full workflow immediately. Idempotent and free of AI/analysis quota."""
    project = ResearchService(db).create_sample(user.id)
    return ResearchProjectOut.model_validate(project)


@router.get("", response_model=list[ResearchProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ResearchProjectOut]:
    projects = ResearchService(db).list_for_user(user.id, limit=limit, offset=offset)
    return [ResearchProjectOut.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ResearchProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchProjectOut:
    project = ResearchService(db).get_owned(project_id, user.id)
    return ResearchProjectOut.model_validate(project)
