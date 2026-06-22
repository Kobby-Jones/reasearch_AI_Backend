from __future__ import annotations

import re
import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

# Heuristics for an academic/institutional email. Not foolproof, but a
# reasonable, low-friction gate for a student discount (no document upload).
_ACADEMIC_PATTERNS = (
    r"\.edu$", r"\.edu\.[a-z]{2}$", r"\.ac\.[a-z]{2}$", r"\.edu\.gh$", r"\.ac\.uk$",
)
_ACADEMIC_KEYWORDS = ("university", "univ", "college", "polytechnic", "institute", "school")


def is_academic_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    if any(re.search(p, domain) for p in _ACADEMIC_PATTERNS):
        return True
    return any(k in domain for k in _ACADEMIC_KEYWORDS)


class GrowthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- student verification ------------------------------------------------
    def verify_student(self, user: User, institution_email: str) -> tuple[bool, int]:
        ok = is_academic_email(institution_email)
        if ok and not user.student_verified:
            user.student_verified = True
            self.db.commit()
        return user.student_verified, (settings.student_discount_pct if user.student_verified else 0)

    # ---- referrals -----------------------------------------------------------
    def ensure_referral_code(self, user: User) -> str:
        if user.referral_code:
            return user.referral_code
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            exists = self.db.scalar(select(User.id).where(User.referral_code == code))
            if not exists:
                user.referral_code = code
                self.db.commit()
                return code
        # extremely unlikely fallback
        user.referral_code = secrets.token_hex(5).upper()
        self.db.commit()
        return user.referral_code

    def referral_count(self, user_id: int) -> int:
        return int(self.db.scalar(
            select(func.count(User.id)).where(User.referred_by_id == user_id)
        ) or 0)

    def referral_link(self, code: str) -> str:
        return f"{settings.frontend_url.rstrip('/')}/register?ref={code}"

    def resolve_referrer(self, code: str | None) -> int | None:
        if not code:
            return None
        uid = self.db.scalar(select(User.id).where(User.referral_code == code.strip().upper()))
        return int(uid) if uid else None
