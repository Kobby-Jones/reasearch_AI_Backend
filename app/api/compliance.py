from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.compliance_templates import templates_for_project

router = APIRouter(prefix="/compliance", tags=["compliance"])


class ComplianceTemplate(BaseModel):
    id: str
    title: str
    body: str


@router.get("/templates", response_model=list[ComplianceTemplate])
def templates(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ComplianceTemplate]:
    return [ComplianceTemplate(**t) for t in templates_for_project(db, user.id, project_id)]
