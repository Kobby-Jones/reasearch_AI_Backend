"""Provider-agnostic interface for the language model.

Every concrete provider implements `generate_text` and `structured_output`.
Higher-level task methods (questionnaire, analyze, chapters, viva) live on
`AIClient` and are built on these two primitives, so adding a provider only
means implementing two methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate_text(
        self, system: str, prompt: str, *, temperature: float = 0.4, max_tokens: int | None = None
    ) -> str:
        ...

    @abstractmethod
    def structured_output(
        self, system: str, prompt: str, *, schema_hint: str = "", temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        ...
