"""Deterministic, dependency-free provider.

Lets the whole platform run end-to-end with no API key. Output is templated but
realistic in *structure* (multi-paragraph markdown, full questionnaire) so the
document generator, analytics, and UI can be exercised and demoed meaningfully
without external credentials. Clearly labelled as mock.
"""
from __future__ import annotations

import re
from typing import Any

from app.ai.base import BaseProvider

_LOREM = (
    "This passage develops the point in coherent academic prose. The configured "
    "language model would synthesise the project's constructs, cite relevant "
    "scholarship, and build a sustained argument across several sentences, "
    "maintaining formal tone and logical flow toward the section's purpose."
)


class MockProvider(BaseProvider):
    name = "mock"

    def generate_text(
        self, system: str, prompt: str, *, temperature: float = 0.4, max_tokens: int | None = None
    ) -> str:
        heading = None
        m = re.search(r"writing \*\*(.+?)\*\*", prompt)
        if m:
            heading = m.group(1)
        m2 = re.search(r"~?(\d+)\s*words", prompt)
        target = int(m2.group(1)) if m2 else 200
        paras = max(2, target // 110)

        out = ["*[Mock AI output — set AI_PROVIDER=openai or claude for real generation.]*"]
        if heading:
            out.append(f"## {heading}")
        for _ in range(paras):
            out.append(_LOREM)
        return "\n\n".join(out)

    def structured_output(
        self, system: str, prompt: str, *, schema_hint: str = "", temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        lower = (system + " " + prompt).lower()
        if "questionnaire" in lower or "likert" in lower:
            return self._mock_questionnaire()
        if "viva" in lower or "examiner" in lower or "defense" in lower:
            return self._mock_viva()
        if "study design" in lower or "objectives" in lower or "hypotheses" in lower:
            return self._mock_topic()
        return {"note": "mock structured output", "schema_hint": schema_hint}

    @staticmethod
    def _mock_topic() -> dict[str, Any]:
        return {
            "variables": {
                "independent": ["Perceived Usefulness", "Perceived Ease of Use"],
                "dependent": ["Adoption Intention"],
                "moderating": ["Facilitating Conditions"],
            },
            "objectives": [
                "To examine the effect of perceived usefulness on adoption intention.",
                "To assess the effect of perceived ease of use on adoption intention.",
                "To determine the moderating role of facilitating conditions.",
            ],
            "hypotheses": [
                "H1: Perceived usefulness significantly predicts adoption intention.",
                "H2: Perceived ease of use significantly predicts adoption intention.",
            ],
            "methodology": {
                "design": "Quantitative cross-sectional survey",
                "population": "Target users of the system under study",
                "sampling": "Stratified random sampling",
                "instrument": "Structured 5-point Likert questionnaire",
                "analysis": ["reliability", "descriptive", "correlation", "regression"],
            },
            "summary": (
                "[Mock] This study investigates the determinants of adoption intention using a "
                "quantitative cross-sectional design. Reliability, descriptive, correlation, and "
                "regression analyses are used to test the hypothesised relationships among the constructs."
            ),
        }

    @staticmethod
    def _mock_questionnaire() -> dict[str, Any]:
        likert = "1=Strongly Disagree, 2=Disagree, 3=Neutral, 4=Agree, 5=Strongly Agree"

        def construct(prefix, name, n):
            items = []
            for i in range(1, n + 1):
                items.append({
                    "id": f"{prefix}{i}",
                    "text": f"[Mock] {name} measurement statement {i}.",
                    "construct": name,
                    "type": "likert",
                    "reverse_coded": bool(i == n),
                })
            return {"id": prefix, "title": name, "construct": name,
                    "instructions": f"Indicate your level of agreement with each statement about {name}.",
                    "items": items}

        return {
            "title": "[Mock] Research Questionnaire",
            "consent": ("You are invited to participate in this academic study. Participation is "
                        "voluntary and anonymous; you may withdraw at any time."),
            "scale": likert,
            "sections": [
                {"id": "A", "title": "Demographic Information", "construct": "demographics",
                 "instructions": "Please tick the option that best describes you.",
                 "items": [
                     {"id": "A1", "text": "Age group", "type": "categorical",
                      "options": ["<20", "20-29", "30-39", "40-49", "50+"]},
                     {"id": "A2", "text": "Gender", "type": "categorical",
                      "options": ["Male", "Female", "Prefer not to say"]},
                     {"id": "A3", "text": "Highest level of education", "type": "categorical",
                      "options": ["Secondary", "Diploma", "Bachelor's", "Postgraduate"]},
                     {"id": "A4", "text": "Years of experience", "type": "categorical",
                      "options": ["<1", "1-3", "4-6", "7+"]},
                 ]},
                construct("B", "Perceived Usefulness", 5),
                construct("C", "Perceived Ease of Use", 5),
                construct("D", "Adoption Intention", 5),
            ],
        }

    @staticmethod
    def _mock_viva() -> dict[str, Any]:
        return {
            "question": ("What is the central contribution of your study, and how does your "
                         "methodology defend its validity?"),
        }
