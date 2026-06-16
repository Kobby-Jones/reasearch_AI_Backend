from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.client import get_ai_client
from app.core.exceptions import NotFoundError
from app.models.viva import VivaSession
from app.repositories.viva_repository import VivaRepository
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.utils.usage_tracker import UsageTracker, AI_CALLS


class VivaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = VivaRepository(db)
        self.ai = get_ai_client()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)

    def _gate(self, user_id: int) -> FeatureGate:
        return FeatureGate(self.subs.current_plan_name(user_id), self.tracker, user_id)

    def start(self, user_id: int, project_id: int, examiner_role: str) -> VivaSession:
        self._gate(user_id).check_viva()  # PREMIUM only
        project = self.research.get_owned(project_id, user_id)

        context = {
            "topic": project.topic,
            "objectives": project.objectives,
            "hypotheses": project.hypotheses,
            "methodology": project.methodology,
        }
        first = self.ai.simulate_viva(context, [], examiner_role)
        self.tracker.increment(user_id, AI_CALLS)

        session = VivaSession(
            project_id=project.id,
            examiner_role=examiner_role,
            status="active",
            transcript=[{"question": first.get("question"), "answer": None,
                         "score": None, "feedback": None}],
        )
        self.repo.add(session)
        self.db.commit()
        return session

    def respond(self, user_id: int, session_id: int, answer: str) -> VivaSession:
        session = self.repo.get(session_id)
        if not session or session.project.user_id != user_id:
            raise NotFoundError("Viva session not found.")
        self._gate(user_id).check_viva()

        transcript = list(session.transcript or [])
        if not transcript:
            raise NotFoundError("No open question to answer.")

        # evaluate the last (open) question
        last = transcript[-1]
        last["answer"] = answer
        evaluation = self.ai.evaluate_viva_answer(last.get("question", ""), answer)
        self.tracker.increment(user_id, AI_CALLS)
        last["score"] = evaluation.get("score")
        last["feedback"] = evaluation.get("feedback")
        last["weak_areas"] = evaluation.get("weak_areas", [])

        # ask the next question
        project = session.project
        context = {"topic": project.topic, "objectives": project.objectives}
        nxt = self.ai.simulate_viva(context, transcript, session.examiner_role)
        self.tracker.increment(user_id, AI_CALLS)
        transcript.append({"question": nxt.get("question"), "answer": None,
                           "score": None, "feedback": None})

        # aggregate readiness from scored turns
        scored = [t["score"] for t in transcript if isinstance(t.get("score"), (int, float))]
        session.readiness_score = int(sum(scored) / len(scored)) if scored else None
        weak = []
        for t in transcript:
            weak.extend(t.get("weak_areas", []) or [])
        session.weak_areas = sorted(set(weak))
        session.transcript = transcript
        self.db.commit()
        return session

    def list_for_project(
        self, user_id: int, project_id: int, limit: int = 100, offset: int = 0
    ) -> list[VivaSession]:
        self.research.get_owned(project_id, user_id)  # ownership guard
        return self.repo.list_for_project(project_id, limit=limit, offset=offset)
