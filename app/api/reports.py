from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.report import ReportRequest
from app.services.report_service import ReportService

router = APIRouter(prefix="/report", tags=["reports"])


@router.post("/generate")
def generate(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    path = ReportService(db).generate(
        user.id, payload.project_id, payload.chapters, payload.fmt,
        payload.include_analysis_ids,
    )
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if payload.fmt == "docx"
        else "application/pdf"
    )
    return FileResponse(path, media_type=media, filename=os.path.basename(path))
