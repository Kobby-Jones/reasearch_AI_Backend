"""Anthropic Claude provider. Imported lazily."""
from __future__ import annotations

import json
import re
from typing import Any

from app.ai.base import BaseProvider
from app.core.config import settings


class ClaudeProvider(BaseProvider):
    name = "claude"

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        import anthropic  # lazy import

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    def generate_text(
        self, system: str, prompt: str, *, temperature: float = 0.4, max_tokens: int | None = None
    ) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens or settings.ai_max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def structured_output(
        self, system: str, prompt: str, *, schema_hint: str = "", temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        sys = system + "\nReturn ONLY a single valid JSON object, no prose, no markdown."
        if schema_hint:
            sys += f"\nExpected shape: {schema_hint}"
        text = self.generate_text(sys, prompt, temperature=temperature, max_tokens=max_tokens)
        return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    text = text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    start = text.find("{")
    if start == -1:
        return {}
    raw = text[start:]
    # 1) try as-is (trim to last closing brace first)
    end = raw.rfind("}")
    if end != -1:
        try:
            return json.loads(raw[: end + 1])
        except json.JSONDecodeError:
            pass
    # 2) try to repair a truncated object by balancing brackets
    repaired = _repair_truncated_json(raw)
    if repaired is not None:
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
    return {}


def _repair_truncated_json(raw: str) -> str | None:
    """Best-effort close of a JSON object that was cut off mid-stream.

    Walks the string tracking string state and the bracket stack, drops any
    trailing partial token, and appends the closing brackets needed to make a
    parseable object. Recovers most ``max_tokens`` truncations.
    """
    stack: list[str] = []
    in_string = False
    escape = False
    last_safe = -1  # index just after the last completed value/structural char

    for i, ch in enumerate(raw):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                last_safe = i
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            last_safe = i
        elif ch in ",":
            last_safe = i - 1  # cut before a dangling comma
        elif ch.isdigit() or ch in "truefalsn.-+eE":
            last_safe = i
        elif ch in " \t\r\n:":
            continue

    if last_safe < 0:
        return None
    candidate = raw[: last_safe + 1].rstrip().rstrip(",")
    # close any still-open structures, innermost first
    closers = "".join(reversed(stack))
    return candidate + closers
