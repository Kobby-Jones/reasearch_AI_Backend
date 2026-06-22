from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuestionnaireGenerateRequest(BaseModel):
    project_id: int
    items_per_section: int = Field(default=5, ge=3, le=15)


class QuestionnaireValidateRequest(BaseModel):
    """Validate either a stored questionnaire (by id) or a raw structure."""

    questionnaire_id: int | None = None
    structure: dict | None = None


class QuestionnaireUpdateRequest(BaseModel):
    """Persist author edits to a questionnaire's structure."""

    structure: dict
    title: str | None = None


class QuestionnaireOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    title: str | None = None
    structure: dict
    clarity_score: int | None = None
    validation: dict | None = None
    created_at: datetime


class ValidationReport(BaseModel):
    clarity_score: int
    issues: list[dict]
    suggestions: list[str]
