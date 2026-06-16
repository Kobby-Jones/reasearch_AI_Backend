"""Mixed-methods workflow.

A convergent mixed-methods study runs BOTH strands on the same project: the
quantitative battery (reliability, descriptives, correlation, regression,
group comparisons, and PLS-PM where applicable) AND thematic analysis of the
free-text responses. Both persist as normal AnalysisResults, so Chapter Four
naturally presents both; the report layer then adds an integration narrative
that triangulates the two.

This service is deliberately thin: it reuses the existing, tested quantitative
and qualitative services rather than reimplementing either.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.auto_analysis_service import AutoAnalysisService
from app.services.qualitative_service import QualitativeService


class MixedMethodsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.quant = AutoAnalysisService(db)
        self.qual = QualitativeService(db)

    def run(
        self, user_id: int, project_id: int, dataset_id: int,
        plan: dict | None = None, text_columns: list[str] | None = None,
    ) -> dict:
        # 1. Quantitative strand (honours a confirmed plan if supplied).
        quant_summary = self.quant.run_full(user_id, project_id, dataset_id, plan=plan)

        # 2. Qualitative strand. If there are no free-text columns, the study is
        #    effectively quantitative-only; we record that rather than failing.
        qual_summary: dict | None = None
        qual_skipped: str | None = None
        try:
            qual_summary = self.qual.run(user_id, project_id, dataset_id, text_columns)
        except Exception as exc:  # no text columns, etc.
            qual_skipped = str(exc)

        steps = list(quant_summary.get("steps_run", []))
        if qual_summary:
            steps.append({"type": "thematic", "themes": qual_summary.get("themes", [])})

        skipped = list(quant_summary.get("skipped", []))
        if qual_skipped:
            skipped.append(f"qualitative ({qual_skipped})")

        return {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "n_observations": quant_summary.get("n_observations", 0),
            "constructs_detected": quant_summary.get("constructs_detected", {}),
            "demographics_detected": quant_summary.get("demographics_detected", []),
            "steps_run": steps,
            "skipped": skipped,
        }
