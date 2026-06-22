from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limit_ip
from app.schemas.survey import PublicSurveyOut, SurveyResponseAck, SurveyResponseIn
from app.services.survey_service import SurveyService

# No authentication: these power the shareable public survey link.
router = APIRouter(prefix="/public/survey", tags=["public-survey"])

_submit_rl = limit_ip("survey_submit", settings.rate_limit_survey_per_hour, 3600)


@router.get("/{token}", response_model=PublicSurveyOut)
def get_public_survey(token: str, db: Session = Depends(get_db)) -> PublicSurveyOut:
    svc = SurveyService(db)
    survey = svc.public_get(token)
    return PublicSurveyOut(
        token=survey.public_token,
        title=survey.title,
        status=survey.status,
        # Serve the questionnaire's current structure so edits made after the
        # link was shared show up immediately for new respondents.
        structure=svc.effective_structure(survey) if survey.status == "open" else {"sections": []},
    )


@router.post("/{token}/respond", response_model=SurveyResponseAck, status_code=201,
             dependencies=[Depends(_submit_rl)])
def submit_public_response(
    token: str,
    payload: SurveyResponseIn,
    db: Session = Depends(get_db),
) -> SurveyResponseAck:
    SurveyService(db).submit_response(token, payload.answers, payload.meta)
    return SurveyResponseAck()
