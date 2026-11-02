"""Construct the configured model provider without exposing secrets."""

from __future__ import annotations

from polyanalyst.config import Settings
from polyanalyst.llm.base import LLMProvider
from polyanalyst.llm.gemini import GeminiProvider


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Return a provider for configured LLM-backed features."""

    provider = settings.model_provider.lower().strip()
    if provider in {"", "demo", "offline"}:
        return None
    if provider in {"gemini", "google", "google-gemini"}:
        api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
        return GeminiProvider(api_key=api_key, model_name=settings.model_name)
    raise ValueError(f"Unsupported model provider: {settings.model_provider}")
