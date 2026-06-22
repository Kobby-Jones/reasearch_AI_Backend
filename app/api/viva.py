from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limit_user
from app.models.user import User
from app.schemas.viva import VivaRespondRequest, VivaSessionOut, VivaStartRequest
from app.services.viva_service import VivaService

router = APIRouter(prefix="/viva", tags=["viva"])

_ai_rl = limit_user("ai", settings.rate_limit_ai_per_min, 60)


@router.post("/start", response_model=VivaSessionOut, status_code=201, dependencies=[Depends(_ai_rl)])
def start(
    payload: VivaStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VivaSessionOut:
    session = VivaService(db).start(user.id, payload.project_id, payload.examiner_role)
    return VivaSessionOut.model_validate(session)


@router.get("", response_model=list[VivaSessionOut])
def list_sessions(
    project_id: int = Query(..., description="List viva sessions for this project"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[VivaSessionOut]:
    sessions = VivaService(db).list_for_project(user.id, project_id, limit=limit, offset=offset)
    return [VivaSessionOut.model_validate(s) for s in sessions]


@router.post("/respond", response_model=VivaSessionOut, dependencies=[Depends(_ai_rl)])
def respond(
    payload: VivaRespondRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VivaSessionOut:
    session = VivaService(db).respond(user.id, payload.session_id, payload.answer)
    return VivaSessionOut.model_validate(session)
