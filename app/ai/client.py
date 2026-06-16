"""AIClient: the single abstraction used by the service layer.

Statistical numbers are NEVER produced here — interpretation and results
narrative only turn already-computed results into prose. Chapters are generated
section by section from the blueprints in `prompts`, which is what gives reports
real depth instead of a few thin pages.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.ai import prompts
from app.ai.base import BaseProvider
from app.core.config import settings


def _citation_instructions(sources_catalog: str) -> str:
    """Build the citation directive injected into writing prompts.

    When a catalog of REAL retrieved sources is available, the writer must cite
    them by key and is forbidden from inventing any others. When no catalog is
    available, the writer must not produce any citations at all (no placeholders
    like '(Author, year)').
    """
    if sources_catalog.strip():
        return (
            "\nCITATIONS — STRICT RULES:\n"
            "- You may cite ONLY from the numbered source list below, using the marker "
            "[[Key]] for a parenthetical citation or [[Key|narrative]] for a narrative one.\n"
            "- Place markers inline exactly where a claim is supported. Cite generously where "
            "claims rest on prior literature.\n"
            "- NEVER write a citation in any other form. NEVER invent authors, years, or sources. "
            "Do NOT write '(Author, year)' or similar placeholders. If no listed source supports a "
            "claim, state it without a citation.\n"
            "- Do NOT use em-dashes; use commas or restructure the sentence.\n\n"
            f"AVAILABLE SOURCES (cite by key):\n{sources_catalog}\n"
        )
    return (
        "\nCITATIONS: No verified source list is available, so do NOT include any citations or "
        "reference placeholders such as '(Author, year)'. Write the prose without citations. "
        "Do NOT use em-dashes; use commas instead.\n"
    )


class AIClient:
    def __init__(self, provider: BaseProvider) -> None:
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.name

    # ---- primitives ---------------------------------------------------------
    def generate_text(
        self, system: str, prompt: str, *, temperature: float = 0.4, max_tokens: int | None = None
    ) -> str:
        return self.provider.generate_text(
            system, prompt, temperature=temperature, max_tokens=max_tokens
        )

    def structured_output(
        self, system: str, prompt: str, *, schema_hint: str = "", temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return self.provider.structured_output(
            system, prompt, schema_hint=schema_hint, temperature=temperature, max_tokens=max_tokens
        )

    # ---- task: research topic breakdown ------------------------------------
    def break_down_topic(self, topic: str, field: str | None) -> dict[str, Any]:
        prompt = (
            f"Research topic: {topic}\nField: {field or 'general'}\n\n"
            "Break this into a rigorous study design as a JSON object with keys:\n"
            "- variables: {independent:[], dependent:[], moderating:[]} (use concrete construct names, "
            "not 'Variable 1')\n"
            "- objectives: [] (1 general + 3-4 specific, each measurable)\n"
            "- hypotheses: [] (directional, falsifiable, labelled H1, H2, ...)\n"
            "- methodology: {design, population, sampling, instrument, analysis:[]}\n"
            "- summary: a 120-160 word abstract-style overview of the proposed study.\n"
            "Make every field specific to THIS topic."
        )
        return self.structured_output(
            prompts.RESEARCH_ASSISTANT,
            prompt,
            schema_hint='{"variables":{"independent":[],"dependent":[],"moderating":[]},'
                        '"objectives":[],"hypotheses":[],"methodology":{},"summary":""}',
            max_tokens=1500,
        )

    # ---- task: questionnaire generation (FULL instrument) ------------------
    def generate_questionnaire(
        self, topic: str, objectives: list, variables: dict | None, items_per_section: int
    ) -> dict[str, Any]:
        per = max(items_per_section, 4)
        prompt = (
            f"Design a COMPLETE, fieldable academic questionnaire for the study: '{topic}'.\n"
            f"Objectives: {json.dumps(objectives)}\n"
            f"Variables: {json.dumps(variables or {})}\n\n"
            "Requirements:\n"
            f"- Section A: Demographics — 5-7 relevant categorical items with options.\n"
            f"- One measurement section PER independent variable AND per dependent variable. "
            f"Name each section after its construct. Each construct section must contain at least "
            f"{per} reflective Likert items that genuinely measure that construct (not generic "
            f"'statement 1'). Include at least one reverse-coded item per construct and flag it.\n"
            "- Use a 5-point Likert scale (1=Strongly Disagree ... 5=Strongly Agree).\n"
            "- Add a short 'instructions' string per section and a 'consent' preamble.\n"
            "- Each Likert item: {id, text, construct, type:'likert', reverse_coded:bool}.\n"
            "Return JSON: {title, consent, scale, sections:[{id, title, construct, instructions, "
            "items:[...]}]}."
        )
        return self.structured_output(
            prompts.QUESTIONNAIRE_DESIGNER,
            prompt,
            schema_hint='{"title":"","consent":"","scale":"","sections":[{"id":"A","title":"",'
                        '"construct":"","instructions":"","items":[]}]}',
            temperature=0.5,
            max_tokens=8000,
        )

    # ---- task: interpret ALREADY-computed statistics -----------------------
    def analyze_research(
        self, analysis_type: str, results: dict, *, advanced: bool = False, context: dict | None = None
    ) -> str:
        depth = (
            "an advanced, thesis-grade interpretation (assumptions, effect size, practical and "
            "theoretical implications, and how it answers the relevant hypothesis)"
            if advanced
            else "a clear standard interpretation (what the test shows, significance, effect size, "
            "and a one-line implication)"
        )
        ctx = f"\nStudy context: {json.dumps(context)}\n" if context else ""
        prompt = (
            f"Analysis type: {analysis_type}{ctx}\n"
            "These results were computed by a deterministic statistics engine. Do NOT change, round, "
            f"or invent any number. Provide {depth}. Reference the exact statistics in APA style.\n\n"
            f"Results:\n{json.dumps(results, indent=2)}"
        )
        return self.generate_text(
            prompts.STAT_INTERPRETER, prompt, temperature=0.3, max_tokens=1200
        )

    # ---- task: report — one focused section --------------------------------
    def write_section(
        self, chapter_title: str, section_title: str, brief: str, context: dict,
        target_words: int, sources_catalog: str = "",
    ) -> str:
        cite_block = _citation_instructions(sources_catalog)
        prompt = (
            f"You are writing **{section_title}** of {chapter_title}.\n\n"
            f"What this section must do: {brief}\n\n"
            f"Write approximately {target_words} words of polished scholarly prose. Begin with the "
            f"'## {section_title}' heading, then the content. Use sub-headings only if natural. Ground "
            "everything ONLY in the project details below; do not invent statistics.\n"
            f"{cite_block}\n"
            f"Project details (JSON):\n{json.dumps(context, indent=2, default=str)}"
        )
        budget = min(4000, int(target_words * 2.2) + 400)
        return self.generate_text(
            prompts.REPORT_WRITER, prompt, temperature=0.55, max_tokens=budget
        )

    # ---- task: report — narrative around a computed result (Ch4) -----------
    def write_results_narrative(
        self, beat: str, analysis_type: str, results: dict, context: dict,
        target_words: int = 220, sources_catalog: str = "",
    ) -> str:
        cite_block = _citation_instructions(sources_catalog)
        prompt = (
            f"Write ~{target_words} words of Chapter Four results narrative for the beat: '{beat}'.\n"
            "A table and/or figure with the exact numbers is shown separately, so DO NOT restate every "
            "number, instead present, interpret, and connect the result to the relevant objective or "
            "hypothesis in flowing prose. You MAY cite the key statistic in APA style. Never invent data.\n"
            f"{cite_block}\n"
            f"Analysis type: {analysis_type}\n"
            f"Computed results (JSON):\n{json.dumps(results, indent=2, default=str)}\n\n"
            f"Study context: {json.dumps(context, default=str)}"
        )
        return self.generate_text(
            prompts.STAT_INTERPRETER, prompt, temperature=0.4, max_tokens=700
        )

    # ---- task: suggested references ----------------------------------------
    def induce_themes(self, responses: list[str], context: dict) -> list[dict]:
        sample = "\n".join(f"- {r}" for r in responses[:60])
        prompt = (
            "You are conducting thematic analysis for a qualitative study.\n"
            f"Study context: {json.dumps(context, default=str)}\n\n"
            "Below are real participant responses. Induce 4 to 7 recurring THEMES that "
            "genuinely appear across them. Ground every theme in the actual text; do not "
            "import themes that are not present. Return JSON only:\n"
            '{"themes":[{"name":"short theme name","definition":"one-sentence definition"}]}\n\n'
            f"Responses:\n{sample}"
        )
        out = self.structured_output(
            prompts.STAT_INTERPRETER, prompt,
            schema_hint='{"themes":[{"name":"","definition":""}]}', max_tokens=900,
        )
        themes = out.get("themes") if isinstance(out, dict) else None
        return themes if isinstance(themes, list) else []

    def code_responses_batch(self, responses: list[str], themes: list[dict], context: dict) -> list[dict]:
        theme_list = "\n".join(f"- {t.get('name')}: {t.get('definition','')}" for t in themes)
        numbered = "\n".join(f"[{i}] {r}" for i, r in enumerate(responses))
        prompt = (
            "Code each participant response against the theme list. For each response, list "
            "which themes apply (use the exact theme names) and copy ONE short supporting quote "
            "(<=25 words) VERBATIM from that same response. Copy the quote exactly as written; "
            "never paraphrase or invent. If no theme applies, return an empty themes list.\n\n"
            f"Themes:\n{theme_list}\n\n"
            f"Responses:\n{numbered}\n\n"
            'Return JSON only: {"coded":[{"i":0,"themes":["..."],"quote":"..."}]}'
        )
        out = self.structured_output(
            prompts.STAT_INTERPRETER, prompt,
            schema_hint='{"coded":[{"i":0,"themes":[],"quote":""}]}',
            max_tokens=min(4000, 200 + len(responses) * 60),
        )
        coded = out.get("coded") if isinstance(out, dict) else None
        # normalise into a per-response list aligned by index
        result = [{"themes": [], "quote": ""} for _ in responses]
        if isinstance(coded, list):
            for item in coded:
                if not isinstance(item, dict):
                    continue
                i = item.get("i")
                if isinstance(i, int) and 0 <= i < len(responses):
                    result[i] = {"themes": item.get("themes") or [], "quote": item.get("quote") or ""}
        return result

    def synthesize_literature(self, catalog: str, topic: str, field: str | None) -> dict:
        prompt = (
            f"Topic: {topic}\nField: {field or 'general'}\n\n"
            "Below is a numbered list of REAL retrieved sources (key, authors, year, title, venue). "
            "Organise them into 4 to 6 coherent literature THEMES. For each theme give a one to two "
            "sentence synthesis of what those works collectively show, and list the source KEYS that "
            "belong to it (use only keys from the list; never invent a key). Then identify 2 to 4 "
            "research GAPS the literature has not resolved. Return JSON only:\n"
            '{"themes":[{"name":"","synthesis":"","sources":["Key1","Key2"]}],"gaps":["",""]}\n\n'
            f"Sources:\n{catalog}"
        )
        out = self.structured_output(
            prompts.STAT_INTERPRETER, prompt,
            schema_hint='{"themes":[{"name":"","synthesis":"","sources":[]}],"gaps":[]}',
            max_tokens=1500,
        )
        return out if isinstance(out, dict) else {"themes": [], "gaps": []}

    def suggest_references(self, topic: str, field: str | None, constructs: list[str]) -> list[str]:
        prompt = (
            f"For a thesis titled '{topic}' in the field of {field or 'general studies'}, list 10-14 "
            f"foundational, well-known scholarly works relevant to these constructs: "
            f"{', '.join(constructs) or 'the study variables'}. Prefer seminal, real, widely-cited "
            "sources. Format each in APA 7th edition. Return JSON: {\"references\": [\"...\", ...]}. "
            "These are suggested starting points the student must verify."
        )
        data = self.structured_output(
            prompts.REPORT_WRITER, prompt, schema_hint='{"references":[]}',
            temperature=0.3, max_tokens=1200,
        )
        refs = data.get("references") or []
        return [r for r in refs if isinstance(r, str) and r.strip()]

    # ---- task: viva simulation ---------------------------------------------
    def simulate_viva(self, context: dict, transcript: list, examiner_role: str) -> dict[str, Any]:
        prompt = (
            f"Examiner role: {examiner_role}\n"
            f"Project context: {json.dumps(context)}\n"
            f"Transcript so far: {json.dumps(transcript)}\n\n"
            'Ask the next probing defense question. Return JSON: {"question": "..."}.'
        )
        return self.structured_output(
            prompts.SUPERVISOR_EXAMINER, prompt, schema_hint='{"question":""}', max_tokens=400
        )

    def evaluate_viva_answer(self, question: str, answer: str) -> dict[str, Any]:
        prompt = (
            f"Question: {question}\nCandidate answer: {answer}\n\n"
            'Evaluate the answer. Return JSON: '
            '{"score": <0-100 int>, "feedback": "...", "weak_areas": ["..."]}.'
        )
        return self.structured_output(
            prompts.SUPERVISOR_EXAMINER,
            prompt,
            schema_hint='{"score":0,"feedback":"","weak_areas":[]}',
            max_tokens=600,
        )

    # ---- legacy single-call chapter (kept for compatibility) ---------------
    def write_chapter(self, chapter: str, context: dict) -> str:
        bp = prompts.CHAPTER_BLUEPRINTS.get(chapter)
        if not bp or not bp["sections"]:
            return self.write_section(
                bp["title"] if bp else f"Chapter {chapter}",
                "Content", "Develop this chapter fully.", context, 800
            )
        parts = []
        for title, brief, words in bp["sections"]:
            parts.append(self.write_section(bp["title"], title, brief, context, words))
        return "\n\n".join(parts)


def _build_provider() -> BaseProvider:
    choice = settings.ai_provider
    if choice == "openai":
        from app.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if choice == "claude":
        from app.ai.claude_provider import ClaudeProvider

        return ClaudeProvider()
    from app.ai.mock_provider import MockProvider

    return MockProvider()


@lru_cache
def get_ai_client() -> AIClient:
    return AIClient(_build_provider())
