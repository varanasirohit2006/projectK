"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr


class Settings(BaseModel):
    """Runtime settings with safe offline defaults."""

    data_dir: Path = Path("data")
    db_path: Path = Path("data/polyanalyst.db")
    model_provider: str = "demo"
    model_name: str = "demo"
    gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    max_sources: int = Field(default=10, ge=1, le=100)
    max_cost_usd: float = Field(default=1.0, ge=0)
    max_duration_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0, le=10)

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from ``POLYANALYST_*`` environment variables."""

        load_dotenv()
        values: dict[str, object] = {}
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        mapping = {
            "data_dir": "POLYANALYST_DATA_DIR",
            "db_path": "POLYANALYST_DB_PATH",
            "model_provider": "POLYANALYST_MODEL_PROVIDER",
            "model_name": "POLYANALYST_MODEL_NAME",
            "max_sources": "POLYANALYST_MAX_SOURCES",
            "max_cost_usd": "POLYANALYST_MAX_COST_USD",
            "max_duration_seconds": "POLYANALYST_MAX_DURATION_SECONDS",
            "max_retries": "POLYANALYST_MAX_RETRIES",
        }
        for field_name, environment_name in mapping.items():
            if environment_name in os.environ:
                values[field_name] = os.environ[environment_name]
        if api_key:
            values["gemini_api_key"] = api_key
            if "POLYANALYST_MODEL_PROVIDER" not in os.environ:
                values["model_provider"] = "gemini"
            if "POLYANALYST_MODEL_NAME" not in os.environ:
                values["model_name"] = "gemma-4-31b-it"
        if values.get("model_provider") in {"gemini", "google", "google-gemini"} and (
            "POLYANALYST_MODEL_NAME" not in os.environ
        ):
            values["model_name"] = "gemma-4-31b-it"
        settings = cls.model_validate(values)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        return settings
