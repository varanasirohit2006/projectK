"""Google Gemini integration using the official ``google-genai`` SDK."""

from __future__ import annotations

import os
from typing import Any

from polyanalyst.llm.base import ModelT


class GeminiConfigurationError(RuntimeError):
    """Raised when the Gemini SDK or API key is unavailable."""


class GeminiGenerationError(RuntimeError):
    """Raised when Gemini cannot produce a valid response."""


class GeminiProvider:
    """Generate text and typed JSON responses with Gemini."""

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if client is not None:
            self._client = client
            return
        if not self._api_key:
            raise GeminiConfigurationError(
                "Set GEMINI_API_KEY or GOOGLE_API_KEY before enabling the Gemini provider"
            )
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise GeminiConfigurationError(
                "Install the Gemini extra with: pip install -e \".[gemini]\""
            ) from exc
        try:
            self._client = genai.Client(api_key=self._api_key)
        except Exception as exc:  # pragma: no cover - SDK/network dependent
            raise GeminiConfigurationError("Could not initialize the Gemini client") from exc

    def generate_text(self, prompt: str, *, system_instruction: str | None = None) -> str:
        config = {"system_instruction": system_instruction} if system_instruction else None
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            text = getattr(response, "text", None)
            if not text:
                raise GeminiGenerationError("Gemini returned an empty response")
            return text
        except GeminiGenerationError:
            raise
        except Exception as exc:
            raise GeminiGenerationError("Gemini text generation failed") from exc

    def generate_structured(
        self,
        prompt: str,
        schema: type[ModelT],
        *,
        system_instruction: str | None = None,
    ) -> ModelT:
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": schema.model_json_schema(),
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            text = getattr(response, "text", None)
            if not text:
                raise GeminiGenerationError("Gemini returned an empty structured response")
            return schema.model_validate_json(text)
        except GeminiGenerationError:
            raise
        except Exception as exc:
            raise GeminiGenerationError("Gemini structured generation failed") from exc
