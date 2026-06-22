"""Import every model so SQLAlchemy's registry/metadata is complete."""
from app.models.base import Base
from app.models.user import User
from app.models.research import ResearchProject
from app.models.questionnaire import Questionnaire
from app.models.dataset import Dataset
from app.models.analysis import AnalysisResult
from app.models.viva import VivaSession
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.usage import UsageRecord
from app.models.survey import Survey, SurveyResponse
from app.models.reference import ProjectReference
from app.models.audit import AuditEvent
from app.models.notification import Notification, SharedReport

__all__ = [
    "Base",
    "User",
    "ResearchProject",
    "Questionnaire",
    "Dataset",
    "AnalysisResult",
    "VivaSession",
    "Subscription",
    "Payment",
    "UsageRecord",
    "Survey",
    "SurveyResponse",
    "ProjectReference",
    "AuditEvent",
    "Notification",
    "SharedReport",
]
