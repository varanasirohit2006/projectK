"""Provider-neutral generation contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMProvider(Protocol):
    """Interface implemented by Gemini and future model providers."""

    provider_name: str
    model_name: str

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> str:
        """Generate plain text from a prompt."""

    def generate_structured(
        self,
        prompt: str,
        schema: type[ModelT],
        *,
        system_instruction: str | None = None,
    ) -> ModelT:
        """Generate and validate a response against a Pydantic schema."""


class CallableLLM:
    """Tiny test adapter for deterministic provider tests."""

    provider_name = "test"
    model_name = "test"

    def __init__(self, structured: Callable[[str, type[ModelT]], ModelT]) -> None:
        self._structured = structured

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> str:
        return prompt

    def generate_structured(
        self,
        prompt: str,
        schema: type[ModelT],
        *,
        system_instruction: str | None = None,
    ) -> ModelT:
        return self._structured(prompt, schema)
