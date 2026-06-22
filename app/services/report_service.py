from __future__ import annotations

import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.client import get_ai_client
from app.ai import prompts
from app.ai.reference_client import build_project_library
from app.ai.references import CitationLibrary
from app.ai.textproc import finalize_prose
from app.core.config import settings
from app.services import report_builder
from app.services.feature_gate import FeatureGate
from app.services.research_service import ResearchService
from app.services.subscription_service import SubscriptionService
from app.analytics import figures
from app.utils.document_generator import generate_docx, generate_pdf, generate_latex
from app.utils.usage_tracker import UsageTracker, AI_CALLS, REPORT_EXPORTS

CHAPTER_TITLES = {
    "1": "Chapter One: Introduction",
    "2": "Chapter Two: Literature Review",
    "3": "Chapter Three: Research Methodology",
    "4": "Chapter Four: Data Presentation, Analysis and Results",
    "5": "Chapter Five: Summary, Conclusions and Recommendations",
}


class ReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ai = get_ai_client()
        self.tracker = UsageTracker(db)
        self.subs = SubscriptionService(db)
        self.research = ResearchService(db)

    # ------------------------------------------------------------------ public
    def _compose(
        self, user_id: int, project_id: int, chapters: list[str],
        include_analysis_ids: list[int] | None,
    ):
        """Build (meta, blocks, gate) shared by every output format."""
        plan_name = self.subs.current_plan_name(user_id)
        gate = FeatureGate(plan_name, self.tracker, user_id)
        gate.check_export()

        project = self.research.get_owned(project_id, user_id)
        analyses = self._gather_analyses(project, include_analysis_ids)
        context = self._base_context(project, analyses)

        from app.services.reference_service import ReferenceService

        library = ReferenceService(self.db).library_for_project(project.id)
        if not library:
            library = build_project_library(
                project.topic, project.field, self._construct_names(project)
            )

        run_id = uuid.uuid4().hex[:8]
        fig_dir = os.path.join(settings.report_dir, "figures", f"{project.id}_{run_id}")
        os.makedirs(fig_dir, exist_ok=True)

        blocks: list[dict] = []
        ordered = [c for c in ("1", "2", "3", "4", "5") if c in chapters]
        for idx, ch in enumerate(ordered):
            if idx > 0:
                blocks.append({"type": "pagebreak"})
            blocks.append({"type": "heading", "text": CHAPTER_TITLES[ch], "level": 1})
            if ch == "4":
                blocks.extend(self._chapter_four(project, analyses, context, fig_dir, user_id, library))
            else:
                blocks.extend(self._narrative_chapter(ch, context, user_id, library))

        refs = library.reference_list(used_only=True)
        if refs:
            blocks.append({"type": "pagebreak"})
            blocks.append({"type": "references", "items": refs})

        return self._meta(project), blocks, gate, project, run_id

    def build_shared_html(
        self, user_id: int, project_id: int, chapters: list[str],
        include_analysis_ids: list[int] | None = None,
    ) -> tuple[str, str]:
        """Render a self-contained HTML report for a public read-only link."""
        from app.utils.document_generator import render_html_body, shared_report_page

        meta, blocks, _gate, _project, _run = self._compose(
            user_id, project_id, chapters, include_analysis_ids
        )
        body = render_html_body(meta, blocks)
        title = meta.get("title", "Research Report")
        return title, shared_report_page(title, body)

    # ---- shareable read-only links ------------------------------------------
    def create_share(
        self, user_id: int, project_id: int, chapters: list[str] | None,
        include_analysis_ids: list[int] | None = None,
    ):
        import secrets

        from app.models.notification import SharedReport

        title, html = self.build_shared_html(
            user_id, project_id, chapters or ["1", "2", "3", "4", "5"], include_analysis_ids
        )
        share = SharedReport(
            user_id=user_id, project_id=project_id,
            token=secrets.token_urlsafe(12), title=title, html=html, revoked=False,
        )
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        return share

    def list_shares(self, user_id: int):
        from sqlalchemy import select

        from app.models.notification import SharedReport

        return list(self.db.scalars(
            select(SharedReport).where(SharedReport.user_id == user_id)
            .order_by(SharedReport.id.desc())
        ).all())

    def revoke_share(self, user_id: int, share_id: int) -> None:
        from app.models.notification import SharedReport

        share = self.db.get(SharedReport, share_id)
        if share and share.user_id == user_id:
            share.revoked = True
            self.db.commit()

    def get_shared_html(self, token: str) -> str | None:
        from sqlalchemy import select

        from app.models.notification import SharedReport

        share = self.db.scalar(select(SharedReport).where(SharedReport.token == token))
        if not share or share.revoked:
            return None
        return share.html

    def generate(
        self, user_id: int, project_id: int, chapters: list[str], fmt: str,
        include_analysis_ids: list[int] | None = None,
    ) -> str:
        meta, blocks, gate, project, run_id = self._compose(
            user_id, project_id, chapters, include_analysis_ids
        )

        os.makedirs(settings.report_dir, exist_ok=True)
        ext = {"docx": "docx", "latex": "tex", "tex": "tex"}.get(fmt, "pdf")
        filename = f"report_{project.id}_{run_id}.{ext}"
        path = os.path.join(settings.report_dir, filename)

        if fmt == "docx":
            generate_docx(path, meta, blocks, watermark=gate.watermark)
        elif fmt in ("latex", "tex"):
            generate_latex(path, meta, blocks, watermark=gate.watermark)
        else:
            generate_pdf(path, meta, blocks, watermark=gate.watermark)

        self.tracker.increment(user_id, REPORT_EXPORTS)
        self.db.commit()
        return path

    # ----------------------------------------------------------- chapter logic
    def _narrative_chapter(
        self, chapter: str, context: dict, user_id: int, library: CitationLibrary
    ) -> list[dict]:
        bp = prompts.CHAPTER_BLUEPRINTS.get(chapter)
        blocks: list[dict] = []
        if not bp or not bp["sections"]:
            return blocks
        catalog = library.catalog_for_prompt() if library else ""
        for title, brief, words in bp["sections"]:
            text = self.ai.write_section(bp["title"], title, brief, context, words, catalog)
            self.tracker.increment(user_id, AI_CALLS)
            blocks.append({"type": "markdown", "text": finalize_prose(text, library)})
        return blocks

    def _chapter_four(
        self, project, analyses: dict, context: dict, fig_dir: str, user_id: int,
        library: CitationLibrary,
    ) -> list[dict]:
        catalog = library.catalog_for_prompt() if library else ""
        blocks: list[dict] = []

        if not analyses:
            text = self.ai.write_section(
                CHAPTER_TITLES["4"],
                "Overview of the Analytical Approach",
                "Explain, based on the stated objectives and hypotheses, how the collected "
                "data will be analysed once available (reliability checks, descriptive "
                "profiling, and the inferential tests mapped to each hypothesis). Make clear "
                "that the empirical results tables will be populated after data collection.",
                context, 500, catalog,
            )
            self.tracker.increment(user_id, AI_CALLS)
            blocks.append({"type": "markdown", "text": finalize_prose(text, library)})
            return blocks

        intro = self.ai.write_results_narrative(
            "an opening that states how this chapter is organised and reminds the reader of "
            "the research objectives the analysis addresses",
            "overview", {"objectives": context.get("objectives"),
                         "hypotheses": context.get("hypotheses")},
            context, target_words=160, sources_catalog=catalog,
        )
        self.tracker.increment(user_id, AI_CALLS)
        blocks.append({"type": "markdown", "text": finalize_prose(intro, library)})

        for atype, heading, beat in report_builder.SECTION_PLAN:
            results = analyses.get(atype)
            if not results:
                continue
            blocks.append({"type": "heading", "text": heading, "level": 2})

            narrative = self.ai.write_results_narrative(beat, atype, results, context, sources_catalog=catalog)
            self.tracker.increment(user_id, AI_CALLS)
            blocks.append({"type": "markdown", "text": finalize_prose(narrative, library)})

            for tbl in report_builder.tables_for(atype, results):
                blocks.append(tbl)

            for fig in figures.figures_for(atype, results, fig_dir):
                blocks.append({
                    "type": "figure",
                    "path": fig.get("path"),
                    "caption": fig.get("caption", ""),
                })

        # Mixed-methods integration: if both a quantitative result and the
        # qualitative themes are present, triangulate them explicitly.
        quant_types = {"regression", "plspm", "correlation", "anova"}
        has_quant = any(t in analyses for t in quant_types)
        has_qual = "thematic" in analyses
        if has_quant and has_qual:
            integration = self.ai.write_results_narrative(
                "an integration of the quantitative and qualitative findings that shows where the "
                "statistical results and the interview themes converge, where they diverge, and how "
                "together they answer the research questions more completely than either strand alone",
                "summary",
                {"quantitative_present": sorted(t for t in quant_types if t in analyses),
                 "themes": [t.get("name") for t in (analyses.get("thematic", {}).get("themes") or [])]},
                context, target_words=260, sources_catalog=catalog,
            )
            self.tracker.increment(user_id, AI_CALLS)
            blocks.append({"type": "heading", "text": "Integration of Quantitative and Qualitative Findings", "level": 2})
            blocks.append({"type": "markdown", "text": finalize_prose(integration, library)})

        summary = self.ai.write_results_narrative(
            "a synthesis that states, for each hypothesis, whether it was supported by the "
            "evidence above and what the overall pattern of results means for the research "
            "objectives",
            "summary",
            {"hypotheses": context.get("hypotheses"),
             "analyses_present": list(analyses.keys())},
            context, target_words=300, sources_catalog=catalog,
        )
        self.tracker.increment(user_id, AI_CALLS)
        blocks.append({"type": "heading", "text": "Summary of Findings", "level": 2})
        blocks.append({"type": "markdown", "text": finalize_prose(summary, library)})
        return blocks

    # ----------------------------------------------------------------- helpers
    def _gather_analyses(self, project, include_ids: list[int] | None = None) -> dict:
        include = set(include_ids) if include_ids else None
        latest: dict[str, dict] = {}
        for ds in project.datasets:
            for a in ds.analyses:
                if include is not None and a.id not in include:
                    continue
                prev = latest.get(a.analysis_type)
                if prev is None or a.id >= prev["_id"]:
                    latest[a.analysis_type] = {"_id": a.id, "results": a.results}
        return {k: v["results"] for k, v in latest.items()}

    def _base_context(self, project, analyses: dict) -> dict:
        return {
            "topic": project.topic,
            "field": project.field,
            "variables": project.variables,
            "objectives": project.objectives,
            "hypotheses": project.hypotheses,
            "methodology": project.methodology,
            "summary": project.summary,
            "analyses_available": list(analyses.keys()),
        }

    def _construct_names(self, project) -> list[str]:
        v = project.variables or {}
        names: list[str] = []
        if isinstance(v, dict):
            for key in ("independent", "dependent", "mediating", "moderating", "constructs"):
                val = v.get(key)
                if isinstance(val, str):
                    names.append(val)
                elif isinstance(val, list):
                    names.extend([str(x) for x in val])
        return [n for n in names if n][:8]

    def _meta(self, project) -> dict:
        owner = getattr(project, "owner", None)
        author = None
        if owner is not None:
            author = getattr(owner, "full_name", None) or getattr(owner, "email", None)
        return {
            "title": project.topic,
            "subtitle": "A Research Report",
            "author": author or "Prepared by the researcher",
            "institution": None,
            "field": f"Field of study: {project.field}" if project.field else None,
            "date": datetime.utcnow().strftime("%B %Y"),
        }
