from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    project_id: int
    chapters: list[Literal["1", "2", "3", "4", "5"]] = Field(
        default=["1", "2", "3", "4", "5"]
    )
    fmt: Literal["pdf", "docx"] = "docx"
    # Optional: restrict Chapter Four to these specific analysis result ids.
    # When omitted, the latest analysis of each type is included automatically.
    include_analysis_ids: list[int] | None = None
