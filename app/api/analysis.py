from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.analysis import (
    AnalysisResultOut,
    AnalysisRunRequest,
    AutoAnalyzeRequest,
    AutoAnalyzeResult,
    InterpretRequest,
    LiteratureReviewRequest,
    MixedMethodsRequest,
    ProposePlanRequest,
    ProposePlanResult,
    QualitativeRequest,
    SecondaryDataRequest,
    StudyTypeProposal,
    StudyTypeRequest,
)
from app.services.analysis_service import AnalysisService
from app.services.auto_analysis_service import AutoAnalysisService
from app.services.literature_review_service import LiteratureReviewService
from app.services.mixed_methods_service import MixedMethodsService
from app.services.qualitative_service import QualitativeService
from app.services.secondary_data_service import SecondaryDataService
from app.services.study_type_service import StudyTypeService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run", response_model=AnalysisResultOut, status_code=201)
def run(
    payload: AnalysisRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisResultOut:
    record = AnalysisService(db).run(user.id, payload.model_dump())
    return AnalysisResultOut.model_validate(record)


@router.get("", response_model=list[AnalysisResultOut])
def list_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    dataset_id: int | None = Query(None, description="Filter by dataset"),
    project_id: int | None = Query(None, description="Filter by project (across its datasets)"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AnalysisResultOut]:
    records = AnalysisService(db).list(
        user.id, dataset_id=dataset_id, project_id=project_id, limit=limit, offset=offset
    )
    return [AnalysisResultOut.model_validate(r) for r in records]


@router.post("/secondary", response_model=AutoAnalyzeResult, status_code=201)
def secondary_data_analyze(
    payload: SecondaryDataRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutoAnalyzeResult:
    """Analyse a non-survey numeric dataset (descriptives, correlation, regression, ANOVA)."""
    summary = SecondaryDataService(db).run(
        user.id, payload.project_id, payload.dataset_id, payload.dependent
    )
    return AutoAnalyzeResult.model_validate(summary)


@router.post("/literature", response_model=AutoAnalyzeResult, status_code=201)
def literature_review_analyze(
    payload: LiteratureReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutoAnalyzeResult:
    """Build a literature synthesis (themes + gaps) from real retrieved sources."""
    summary = LiteratureReviewService(db).run(user.id, payload.project_id)
    return AutoAnalyzeResult.model_validate(summary)


@router.post("/mixed", response_model=AutoAnalyzeResult, status_code=201)
def mixed_methods_analyze(
    payload: MixedMethodsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutoAnalyzeResult:
    """Run both the quantitative battery and qualitative thematic analysis."""
    plan = payload.plan.model_dump() if payload.plan else None
    summary = MixedMethodsService(db).run(
        user.id, payload.project_id, payload.dataset_id, plan=plan,
        text_columns=payload.text_columns,
    )
    return AutoAnalyzeResult.model_validate(summary)


@router.post("/qualitative", response_model=AutoAnalyzeResult, status_code=201)
def qualitative_analyze(
    payload: QualitativeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutoAnalyzeResult:
    """Run thematic analysis over a project's free-text responses."""
    summary = QualitativeService(db).run(
        user.id, payload.project_id, payload.dataset_id, payload.text_columns
    )
    # shape into the shared AutoAnalyzeResult envelope
    return AutoAnalyzeResult.model_validate({
        "project_id": summary["project_id"],
        "dataset_id": summary["dataset_id"],
        "n_observations": summary["n_responses"],
        "constructs_detected": {},
        "demographics_detected": [],
        "steps_run": [{"type": "thematic", "themes": summary["themes"]}],
        "skipped": [],
    })


@router.post("/study-type", response_model=StudyTypeProposal)
def detect_study_type(
    payload: StudyTypeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StudyTypeProposal:
    """Propose what kind of study this is (survey, qualitative, mixed, secondary,
    review) so the right analysis workflow can be offered. The student confirms."""
    result = StudyTypeService(db).propose(user.id, payload.project_id)
    return StudyTypeProposal.model_validate(result)


@router.post("/propose", response_model=ProposePlanResult)
def propose_plan(
    payload: ProposePlanRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposePlanResult:
    """Detect the analysis plan for review/correction. No run, no quota used."""
    plan = AutoAnalysisService(db).propose_plan(user.id, payload.project_id, payload.dataset_id)
    return ProposePlanResult.model_validate(plan)


@router.post("/auto", response_model=AutoAnalyzeResult, status_code=201)
def auto_analyze(
    payload: AutoAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AutoAnalyzeResult:
    """Run the full standard analysis battery for a project's dataset in one call."""
    plan = payload.plan.model_dump() if payload.plan else None
    summary = AutoAnalysisService(db).run_full(
        user.id, payload.project_id, payload.dataset_id, plan=plan
    )
    return AutoAnalyzeResult.model_validate(summary)


@router.post("/interpret", response_model=AnalysisResultOut)
def interpret(
    payload: InterpretRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisResultOut:
    record = AnalysisService(db).interpret(user.id, payload.analysis_id, payload.style)
    return AnalysisResultOut.model_validate(record)
