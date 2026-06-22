from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import limit_user
from app.models.user import User
from app.schemas.questionnaire import (
    QuestionnaireGenerateRequest,
    QuestionnaireOut,
    QuestionnaireUpdateRequest,
    QuestionnaireValidateRequest,
    ValidationReport,
)
from app.services.questionnaire_service import QuestionnaireService

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])

_ai_rl = limit_user("ai", settings.rate_limit_ai_per_min, 60)


@router.get("/{questionnaire_id}/xlsform")
def export_xlsform(
    questionnaire_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download the instrument as an XLSForm for KoboToolbox / ODK."""
    import os
    import tempfile

    from fastapi.responses import FileResponse

    from app.services.research_service import ResearchService
    from app.repositories.questionnaire_repository import QuestionnaireRepository
    from app.services.xlsform import build_xlsform

    q = QuestionnaireRepository(db).get(questionnaire_id)
    if q is None:
        raise HTTPException(404, "Questionnaire not found.")
    ResearchService(db).get_owned(q.project_id, user.id)

    out_dir = tempfile.mkdtemp(prefix="rai_xls_")
    path = os.path.join(out_dir, "instrument_xlsform.xlsx")
    build_xlsform(q.structure, q.title or "Research Survey", path)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="instrument_xlsform.xlsx",
    )


@router.put("/{questionnaire_id}", response_model=QuestionnaireOut)
def update_questionnaire(
    questionnaire_id: int,
    payload: QuestionnaireUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuestionnaireOut:
    q = QuestionnaireService(db).update_structure(
        user.id, questionnaire_id, payload.structure, payload.title
    )
    return QuestionnaireOut.model_validate(q)


@router.post("/generate", response_model=QuestionnaireOut, status_code=201, dependencies=[Depends(_ai_rl)])
def generate(
    payload: QuestionnaireGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuestionnaireOut:
    q = QuestionnaireService(db).generate(
        user.id, payload.project_id, payload.items_per_section
    )
    return QuestionnaireOut.model_validate(q)


@router.get("", response_model=list[QuestionnaireOut])
def list_questionnaires(
    project_id: int = Query(..., description="List questionnaires for this project"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[QuestionnaireOut]:
    items = QuestionnaireService(db).list_for_project(user.id, project_id, limit=limit, offset=offset)
    return [QuestionnaireOut.model_validate(q) for q in items]


@router.post("/validate", response_model=ValidationReport)
def validate(
    payload: QuestionnaireValidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationReport:
    report = QuestionnaireService(db).validate(
        user.id,
        structure=payload.structure,
        questionnaire_id=payload.questionnaire_id,
    )
    return ValidationReport(**report)
