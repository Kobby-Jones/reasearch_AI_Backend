from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.questionnaire import (
    QuestionnaireGenerateRequest,
    QuestionnaireOut,
    QuestionnaireValidateRequest,
    ValidationReport,
)
from app.services.questionnaire_service import QuestionnaireService

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])


@router.post("/generate", response_model=QuestionnaireOut, status_code=201)
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
