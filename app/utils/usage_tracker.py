"""Usage tracking helper — increments per-user, per-month metric counters."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.usage_repository import UsageRepository

AI_CALLS = "ai_calls"
ANALYSIS_RUNS = "analysis_runs"
QUESTIONNAIRE_GENS = "questionnaire_generations"
REPORT_EXPORTS = "report_exports"


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class UsageTracker:
    def __init__(self, db: Session) -> None:
        self.repo = UsageRepository(db)

    def increment(self, user_id: int, metric: str, by: int = 1) -> int:
        rec = self.repo.get_or_create(user_id, metric, current_period())
        rec.count += by
        self.repo.db.flush()
        return rec.count

    def get(self, user_id: int, metric: str) -> int:
        rec = self.repo.get_or_create(user_id, metric, current_period())
        return rec.count

    def totals(self, user_id: int) -> dict[str, int]:
        return self.repo.totals_for_user(user_id, current_period())
