from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.client import get_ai_client
from app.core.exceptions import AIGenerationError, NotFoundError, ValidationError
from app.models.questionnaire import Questionnaire
from app.repositories.questionnaire_repository import QuestionnaireRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.utils.usage_tracker import (
    UsageTracker,
    AI_CALLS,
    QUESTIONNAIRE_GENS,
)


class QuestionnaireService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = QuestionnaireRepository(db)
        self.ai = get_ai_client()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)

    def _gate(self, user_id: int) -> FeatureGate:
        return FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)

    def generate(self, user_id: int, project_id: int, items_per_section: int) -> Questionnaire:
        gate = self._gate(user_id)
        gate.check_questionnaire()  # plan-based restriction enforced here

        project = self.research.get_owned(project_id, user_id)

        # Generate, retrying once if the model returns an empty/unparseable
        # instrument. Usage is NOT counted until we have a usable result, so a
        # failed generation never consumes the user's quota.
        structure = None
        for _ in range(2):
            candidate = self.ai.generate_questionnaire(
                project.topic, project.objectives or [], project.variables, items_per_section
            )
            if _has_sections(candidate):
                structure = candidate
                break

        if structure is None:
            # nothing stored, nothing charged
            raise AIGenerationError(
                "The questionnaire could not be generated this time and you have not "
                "been charged for it. Please try again in a moment."
            )

        self.tracker.increment(user_id, AI_CALLS)
        self.tracker.increment(user_id, QUESTIONNAIRE_GENS)

        validation = validate_structure(structure)
        q = Questionnaire(
            project_id=project.id,
            title=structure.get("title"),
            structure=structure,
            clarity_score=validation["clarity_score"],
            validation=validation,
        )
        self.repo.add(q)
        self.db.commit()
        return q

    def validate(
        self,
        user_id: int,
        structure: dict | None = None,
        questionnaire_id: int | None = None,
    ) -> dict:
        if structure is None and questionnaire_id is None:
            raise ValidationError("Provide either questionnaire_id or structure.")
        if structure is None:
            q = self.repo.get(questionnaire_id)
            if q is None:
                raise NotFoundError("Questionnaire not found.")
            # ownership check via the parent project
            self.research.get_owned(q.project_id, user_id)
            structure = q.structure
            report = validate_structure(structure)
            q.clarity_score = report["clarity_score"]
            q.validation = report
            self.db.commit()
            return report
        return validate_structure(structure)

    def list_for_project(
        self, user_id: int, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[Questionnaire]:
        self.research.get_owned(project_id, user_id)  # ownership guard
        return self.repo.list_for_project(project_id, limit=limit, offset=offset)


# --- deterministic validator (no AI) ---------------------------------------
_LEADING = ("don't you agree", "isn't it true", "shouldn't", "obviously", "clearly")
_DOUBLE = (" and ", " or ", "/")


def _has_sections(structure: dict | None) -> bool:
    """True only if the structure carries at least one section with items."""
    if not isinstance(structure, dict):
        return False
    sections = structure.get("sections")
    if not isinstance(sections, list) or not sections:
        return False
    return any(isinstance(s, dict) and s.get("items") for s in sections)


def validate_structure(structure: dict) -> dict:
    issues: list[dict] = []
    suggestions: list[str] = []
    items = _collect_items(structure)
    sections = {s.get("id") for s in structure.get("sections", [])}

    for item in items:
        text = (item.get("text") or "").lower()
        if any(p in text for p in _LEADING):
            issues.append({"item": item.get("id"), "type": "leading", "text": item.get("text")})
        # Only flag double-barrelled for Likert/statement items (not demographics).
        if item.get("type") == "likert" and any(d in text for d in _DOUBLE) and len(text.split()) > 10:
            issues.append({"item": item.get("id"), "type": "double_barrelled", "text": item.get("text")})
        if len(text.split()) < 3 and item.get("type") == "likert":
            issues.append({"item": item.get("id"), "type": "ambiguous", "text": item.get("text")})

    # Need a demographics section (A) plus at least two construct sections.
    construct_sections = [s for s in structure.get("sections", []) if s.get("id") not in (None, "A")]
    if "A" not in sections:
        issues.append({"section": "A", "type": "missing_demographics"})
        suggestions.append("Add Section A for demographic items.")
    if len(construct_sections) < 2:
        issues.append({"section": "constructs", "type": "insufficient_constructs"})
        suggestions.append("Add a measurement section for each independent and dependent variable.")

    penalty = min(100, len(issues) * 12)
    clarity = max(0, 100 - penalty)
    if issues and not suggestions:
        suggestions.append("Revise flagged items to remove bias and ambiguity.")

    return {"clarity_score": clarity, "issues": issues, "suggestions": suggestions}


def _collect_items(structure: dict) -> list[dict]:
    items: list[dict] = []
    for section in structure.get("sections", []):
        items.extend(section.get("items", []))
    return items
