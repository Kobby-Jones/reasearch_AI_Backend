from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SurveyCreate(BaseModel):
    questionnaire_id: int
    title: str | None = Field(default=None, max_length=255)


class SurveyOut(BaseModel):
    """Owner-facing view of a survey, including live response count and link."""

    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    questionnaire_id: int
    public_token: str
    title: str | None = None
    status: str
    created_at: datetime
    closed_at: datetime | None = None
    response_count: int = 0
    public_url: str | None = None


class PublicSurveyOut(BaseModel):
    """Respondent-facing view: only what's needed to render and fill the form."""

    token: str
    title: str | None = None
    status: str
    structure: dict


class SurveyResponseIn(BaseModel):
    answers: dict
    meta: dict | None = None


class SurveyResponseAck(BaseModel):
    ok: bool = True
    message: str = "Thank you. Your response has been recorded."


class SurveyResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    answers: dict
    created_at: datetime
