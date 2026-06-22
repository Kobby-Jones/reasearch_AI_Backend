from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.report import ReportRequest
from app.services.report_service import ReportService
from pydantic import BaseModel

router = APIRouter(prefix="/report", tags=["reports"])


class ShareRequest(BaseModel):
    project_id: int
    chapters: list[str] | None = None
    include_analysis_ids: list[int] | None = None


class ShareOut(BaseModel):
    id: int
    token: str
    title: str | None = None
    url: str
    revoked: bool


def _share_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/r/{token}"


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
        else "application/x-tex"
        if payload.fmt == "latex"
        else "application/pdf"
    )
    from app.services.audit_service import audit
    audit(db, user.id, "report.export", target_type="project", target_id=payload.project_id,
          summary=f"Exported {payload.fmt.upper()} report")
    from app.services.notification_service import notify
    notify(db, user.id, "Your report is ready",
           body=f"Your {payload.fmt.upper()} report has been generated and downloaded.",
           type="success", link="/reports")
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


@router.post("/share", response_model=ShareOut, status_code=201)
def create_share(
    payload: ShareRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ShareOut:
    share = ReportService(db).create_share(
        user.id, payload.project_id, payload.chapters, payload.include_analysis_ids
    )
    from app.services.audit_service import audit
    audit(db, user.id, "report.share", target_type="project", target_id=payload.project_id,
          summary="Created a shareable report link")
    return ShareOut(id=share.id, token=share.token, title=share.title,
                    url=_share_url(share.token), revoked=share.revoked)


@router.get("/shares", response_model=list[ShareOut])
def list_shares(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ShareOut]:
    shares = ReportService(db).list_shares(user.id)
    return [ShareOut(id=s.id, token=s.token, title=s.title, url=_share_url(s.token), revoked=s.revoked)
            for s in shares]


@router.post("/shares/{share_id}/revoke", status_code=204, response_class=Response)
def revoke_share(
    share_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    ReportService(db).revoke_share(user.id, share_id)
    return Response(status_code=204)
