"""OpenAI provider. Imported lazily so the package is optional at runtime."""
from __future__ import annotations

import json
from typing import Any

from app.ai.base import BaseProvider
from app.core.config import settings


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        from openai import OpenAI  # lazy import

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def generate_text(
        self, system: str, prompt: str, *, temperature: float = 0.4, max_tokens: int | None = None
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens or settings.ai_max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""

    def structured_output(
        self, system: str, prompt: str, *, schema_hint: str = "", temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        sys = system + "\nRespond with a single valid JSON object and nothing else."
        if schema_hint:
            sys += f"\nExpected shape: {schema_hint}"
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens or settings.ai_max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": prompt},
            ],
        )
        return json.loads(resp.choices[0].message.content or "{}")
