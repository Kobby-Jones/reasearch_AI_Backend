from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VivaStartRequest(BaseModel):
    project_id: int
    examiner_role: Literal["supervisor", "external_examiner"] = "supervisor"


class VivaRespondRequest(BaseModel):
    session_id: int
    answer: str


class VivaTurnOut(BaseModel):
    question: str
    answer: str | None = None
    score: int | None = None
    feedback: str | None = None


class VivaSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    examiner_role: str
    status: str
    transcript: list
    readiness_score: int | None = None
    weak_areas: list | None = None
    created_at: datetime
