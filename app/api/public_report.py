from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.report_service import ReportService

# No authentication: powers the public, read-only shared report link.
router = APIRouter(prefix="/public/report", tags=["public-report"])


@router.get("/{token}", response_class=HTMLResponse)
def view_shared_report(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    html = ReportService(db).get_shared_html(token)
    if html is None:
        raise HTTPException(404, "This report link is invalid or has been revoked.")
    return HTMLResponse(content=html)
