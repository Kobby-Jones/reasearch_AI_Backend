from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    filename: str
    row_count: int
    column_count: int
    schema_info: dict | None = None
    cleaning_report: dict | None = None
    version: int = 1
    supersedes_id: int | None = None
    created_at: datetime
