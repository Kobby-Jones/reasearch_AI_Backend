"""Plan definitions + feature gating. ALL access control lives in the service
layer and is funnelled through this module."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import FeatureLockedError, UsageLimitError
from app.utils import usage_tracker as ut
from app.utils.usage_tracker import UsageTracker

UNLIMITED = -1


@dataclass(frozen=True)
class Plan:
    name: str
    questionnaire_per_month: int
    analysis_runs_per_month: int
    can_export: bool
    watermark: bool
    advanced_interpretation: bool
    viva_simulation: bool
    priority: bool
    features: list[str] = field(default_factory=list)


PLANS: dict[str, Plan] = {
    "free": Plan(
        name="free",
        questionnaire_per_month=3,
        analysis_runs_per_month=5,
        can_export=True,
        watermark=True,
        advanced_interpretation=False,
        viva_simulation=False,
        priority=False,
        features=["Limited questionnaire generation", "Limited analysis", "Watermarked reports"],
    ),
    "basic": Plan(
        name="basic",
        questionnaire_per_month=UNLIMITED,
        analysis_runs_per_month=UNLIMITED,
        can_export=True,
        watermark=False,
        advanced_interpretation=False,
        viva_simulation=False,
        priority=False,
        features=[
            "Unlimited questionnaire generation",
            "Full statistical analysis",
            "PDF/DOCX exports",
            "Standard AI interpretation",
        ],
    ),
    "premium": Plan(
        name="premium",
        questionnaire_per_month=UNLIMITED,
        analysis_runs_per_month=UNLIMITED,
        can_export=True,
        watermark=False,
        advanced_interpretation=True,
        viva_simulation=True,
        priority=True,
        features=[
            "Everything in Basic",
            "Advanced AI interpretation",
            "Viva simulation (defense coaching)",
            "Enhanced thesis-style report generation",
            "Priority processing",
        ],
    ),
}


def get_plan(name: str | None) -> Plan:
    return PLANS.get((name or "free").lower(), PLANS["free"])


class FeatureGate:
    """Enforces plan limits. Raises FeatureLockedError / UsageLimitError."""

    def __init__(self, plan_name: str | None, tracker: UsageTracker, user_id: int) -> None:
        self.plan = get_plan(plan_name)
        self.tracker = tracker
        self.user_id = user_id

    def _check_quota(self, metric: str, limit: int) -> None:
        if limit == UNLIMITED:
            return
        used = self.tracker.get(self.user_id, metric)
        if used >= limit:
            self._warn_once(metric, limit)
            raise UsageLimitError(
                f"Monthly limit reached for {metric} on the '{self.plan.name}' plan "
                f"({used}/{limit}). Upgrade to continue."
            )

    _METRIC_LABELS = {
        ut.QUESTIONNAIRE_GENS: "questionnaire generations",
        ut.ANALYSIS_RUNS: "analysis runs",
        ut.REPORT_EXPORTS: "report exports",
    }

    def _warn_once(self, metric: str, limit: int) -> None:
        """Email the user the first time they hit a given limit in a period."""
        try:
            sentinel = f"warn_{metric}"
            # increment returns the new count; only the 0->1 transition emails
            if self.tracker.increment(self.user_id, sentinel) != 1:
                return
            from app.repositories.user_repository import UserRepository
            from app.services.email_service import email_service

            user = UserRepository(self.tracker.repo.db).get(self.user_id)
            if user:
                email_service.send_quota_warning(
                    user.email, self._METRIC_LABELS.get(metric, metric), limit
                )
        except Exception:
            pass

    def check_questionnaire(self) -> None:
        self._check_quota(ut.QUESTIONNAIRE_GENS, self.plan.questionnaire_per_month)

    def check_analysis(self) -> None:
        self._check_quota(ut.ANALYSIS_RUNS, self.plan.analysis_runs_per_month)

    def check_export(self) -> None:
        if not self.plan.can_export:
            raise FeatureLockedError("Report export is not available on your plan.")

    def check_advanced_interpretation(self) -> None:
        if not self.plan.advanced_interpretation:
            raise FeatureLockedError(
                "Advanced AI interpretation is a PREMIUM feature."
            )

    def check_viva(self) -> None:
        if not self.plan.viva_simulation:
            raise FeatureLockedError("Viva simulation is a PREMIUM feature.")

    @property
    def watermark(self) -> bool:
        return self.plan.watermark
