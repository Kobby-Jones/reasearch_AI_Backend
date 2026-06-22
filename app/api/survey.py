from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.dataset import DatasetOut
from app.schemas.survey import (
    SurveyCreate,
    SurveyOut,
    SurveyResponseOut,
)
from app.services.survey_service import SurveyService

router = APIRouter(prefix="/survey", tags=["survey"])


@router.post("", response_model=SurveyOut, status_code=201)
def create_survey(
    payload: SurveyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SurveyOut:
    svc = SurveyService(db)
    survey = svc.create(user.id, payload.questionnaire_id, payload.title)
    return SurveyOut(**svc.serialize(survey))


@router.get("", response_model=list[SurveyOut])
def list_surveys(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SurveyOut]:
    svc = SurveyService(db)
    return [SurveyOut(**svc.serialize(s)) for s in svc.list_for_project(user.id, project_id)]


@router.get("/{survey_id}", response_model=SurveyOut)
def get_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SurveyOut:
    svc = SurveyService(db)
    return SurveyOut(**svc.serialize(svc.get_owned(survey_id, user.id)))


@router.post("/{survey_id}/close", response_model=SurveyOut)
def close_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SurveyOut:
    svc = SurveyService(db)
    return SurveyOut(**svc.serialize(svc.set_status(user.id, survey_id, "closed")))


@router.post("/{survey_id}/reopen", response_model=SurveyOut)
def reopen_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SurveyOut:
    svc = SurveyService(db)
    return SurveyOut(**svc.serialize(svc.set_status(user.id, survey_id, "open")))


@router.get("/{survey_id}/responses", response_model=list[SurveyResponseOut])
def list_responses(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SurveyResponseOut]:
    svc = SurveyService(db)
    return [SurveyResponseOut.model_validate(r) for r in svc.list_responses(user.id, survey_id)]


@router.get("/{survey_id}/analytics")
def survey_analytics(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Per-question response analytics for the results dashboard."""
    return SurveyService(db).analytics(user.id, survey_id)


@router.post("/{survey_id}/import", response_model=DatasetOut, status_code=201)
def import_responses(
    survey_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatasetOut:
    """Materialise collected responses into a cleaned dataset for analysis."""
    svc = SurveyService(db)
    dataset = svc.import_to_dataset(user.id, survey_id)
    return DatasetOut.model_validate(dataset)
