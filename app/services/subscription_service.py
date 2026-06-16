from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.repositories.subscription_repository import SubscriptionRepository
from app.services.feature_gate import get_plan
from app.utils.usage_tracker import UsageTracker


class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SubscriptionRepository(db)
        self.tracker = UsageTracker(db)

    def current_plan_name(self, user_id: int) -> str:
        sub = self.repo.active_for_user(user_id)
        if sub and self._is_valid(sub):
            return sub.plan
        return "free"

    def _is_valid(self, sub: Subscription) -> bool:
        if sub.status != "active":
            return False
        if sub.end_date and self._as_utc(sub.end_date) < datetime.now(timezone.utc):
            sub.status = "expired"
            self.db.flush()
            return False
        return True

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        # SQLite returns naive datetimes; treat stored values as UTC so they can
        # be compared safely against an aware "now".
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def activate(self, user_id: int, plan: str, interval: str = "monthly") -> Subscription:
        # expire any existing active subscription
        existing = self.repo.active_for_user(user_id)
        if existing:
            existing.status = "cancelled"
            self.db.flush()

        now = datetime.now(timezone.utc)
        days = 365 if interval == "annual" else 30
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            start_date=now,
            end_date=now + timedelta(days=days),
            interval=interval,
            cancel_at_period_end=False,
        )
        self.repo.add(sub)
        self.db.commit()
        return sub

    def cancel(self, user_id: int) -> dict:
        """Flag the active subscription to lapse at period end (no refund, keeps access)."""
        sub = self.repo.active_for_user(user_id)
        if sub and self._is_valid(sub):
            sub.cancel_at_period_end = True
            self.db.commit()
        return self.status(user_id)

    def resume(self, user_id: int) -> dict:
        """Reverse a pending cancellation so the plan renews as normal."""
        sub = self.repo.active_for_user(user_id)
        if sub and self._is_valid(sub):
            sub.cancel_at_period_end = False
            self.db.commit()
        return self.status(user_id)

    def status(self, user_id: int) -> dict:
        plan_name = self.current_plan_name(user_id)
        sub = self.repo.active_for_user(user_id)
        plan = get_plan(plan_name)
        return {
            "plan": plan_name,
            "status": sub.status if sub else "active",
            "start_date": sub.start_date if sub else None,
            "end_date": sub.end_date if sub else None,
            "interval": getattr(sub, "interval", None) if sub else None,
            "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)) if sub else False,
            "usage": self.tracker.totals(user_id),
            "limits": {
                "questionnaire_per_month": plan.questionnaire_per_month,
                "analysis_runs_per_month": plan.analysis_runs_per_month,
                "viva_simulation": plan.viva_simulation,
                "advanced_interpretation": plan.advanced_interpretation,
            },
        }
