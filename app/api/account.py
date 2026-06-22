from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.account_export_service import AccountExportService
from app.services.audit_service import audit
from app.services.growth_service import GrowthService
from pydantic import BaseModel

router = APIRouter(prefix="/account", tags=["account"])


class VerifyStudentRequest(BaseModel):
    institution_email: str


class VerifyStudentResult(BaseModel):
    verified: bool
    discount_pct: int
    message: str


class ReferralOut(BaseModel):
    code: str
    url: str
    referral_count: int


@router.post("/verify-student", response_model=VerifyStudentResult)
def verify_student(
    payload: VerifyStudentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VerifyStudentResult:
    verified, pct = GrowthService(db).verify_student(user, payload.institution_email)
    return VerifyStudentResult(
        verified=verified, discount_pct=pct,
        message=(f"Verified. A {pct}% student discount applies to your subscription."
                 if verified else
                 "That email isn't recognised as an academic address. Use your university email (e.g. ending in .edu or .edu.gh)."),
    )


@router.get("/referral", response_model=ReferralOut)
def referral(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ReferralOut:
    svc = GrowthService(db)
    code = svc.ensure_referral_code(user)
    return ReferralOut(code=code, url=svc.referral_link(code), referral_count=svc.referral_count(user.id))


@router.get("/export")
def export_account(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    """Download a complete ZIP of all data associated with the account."""
    path = AccountExportService(db).build(user)
    audit(db, user.id, "account.export", summary="Exported account data")
    return FileResponse(path, media_type="application/zip", filename="researchai-export.zip")
