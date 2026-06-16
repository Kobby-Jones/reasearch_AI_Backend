from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TopicRequest(BaseModel):
    topic: str = Field(min_length=5, max_length=512)
    field: str | None = Field(default=None, description="Discipline, e.g. 'Public Health'")


class ResearchProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic: str
    field: str | None = None
    variables: dict | None = None
    objectives: list | None = None
    hypotheses: list | None = None
    methodology: dict | None = None
    summary: str | None = None
    is_sample: bool = False
    created_at: datetime
