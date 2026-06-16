from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnalysisType = Literal[
    "descriptive", "correlation", "regression", "anova", "frequency", "reliability"
]


class AnalysisRunRequest(BaseModel):
    dataset_id: int
    analysis_type: AnalysisType
    # Column selections — meaning depends on analysis_type.
    columns: list[str] | None = Field(default=None, description="Target columns")
    dependent: str | None = None
    independents: list[str] | None = None
    group_column: str | None = None
    constructs: dict[str, list[str]] | None = Field(
        default=None, description="Construct -> item columns (for reliability)"
    )
    method: Literal["pearson", "spearman"] = "pearson"


class QualitativeRequest(BaseModel):
    project_id: int
    dataset_id: int
    text_columns: list[str] | None = None


class StudyTypeRequest(BaseModel):
    project_id: int


class StudyTypeProposal(BaseModel):
    project_id: int
    study_type: str
    study_type_label: str
    confidence: float
    reasons: list[str]
    scores: dict[str, float]
    workflow: str
    available_types: dict[str, str]
    data_summary: list[dict] = Field(default_factory=list)


class StructuralModel(BaseModel):
    outcome: str | None = None
    predictors: list[str] = Field(default_factory=list)


class AnalysisPlan(BaseModel):
    constructs: dict[str, list[str]] = Field(default_factory=dict)
    demographics: list[str] = Field(default_factory=list)
    structural: StructuralModel = Field(default_factory=StructuralModel)


class SecondaryDataRequest(BaseModel):
    project_id: int
    dataset_id: int
    dependent: str | None = None


class LiteratureReviewRequest(BaseModel):
    project_id: int


class MixedMethodsRequest(BaseModel):
    project_id: int
    dataset_id: int
    plan: AnalysisPlan | None = None
    text_columns: list[str] | None = None


class ProposePlanRequest(BaseModel):
    project_id: int
    dataset_id: int


class ColumnInfo(BaseModel):
    name: str
    numeric: bool
    unique: int


class ProposePlanResult(BaseModel):
    project_id: int
    dataset_id: int
    n_observations: int
    columns: list[ColumnInfo]
    constructs: dict[str, list[str]]
    demographics: list[str]
    structural: StructuralModel


class AutoAnalyzeRequest(BaseModel):
    project_id: int
    dataset_id: int
    plan: AnalysisPlan | None = None


class AutoAnalyzeResult(BaseModel):
    project_id: int
    dataset_id: int
    n_observations: int
    constructs_detected: dict[str, list[str]]
    demographics_detected: list[str]
    steps_run: list[dict]
    skipped: list[str]


class AnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dataset_id: int
    analysis_type: str
    parameters: dict | None = None
    results: dict
    interpretation: str | None = None
    created_at: datetime


class InterpretRequest(BaseModel):
    analysis_id: int
    style: Literal["standard", "advanced"] = "standard"
