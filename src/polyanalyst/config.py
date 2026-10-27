"""Typed application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime settings with safe offline defaults."""

    data_dir: Path = Path("data")
    db_path: Path = Path("data/polyanalyst.db")
    model_provider: str = "demo"
    model_name: str = "demo"
    max_sources: int = Field(default=10, ge=1, le=100)
    max_cost_usd: float = Field(default=1.0, ge=0)
    max_duration_seconds: int = Field(default=300, ge=1)

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from ``POLYANALYST_*`` environment variables."""

        values: dict[str, object] = {}
        mapping = {
            "data_dir": "POLYANALYST_DATA_DIR",
            "db_path": "POLYANALYST_DB_PATH",
            "model_provider": "POLYANALYST_MODEL_PROVIDER",
            "model_name": "POLYANALYST_MODEL_NAME",
            "max_sources": "POLYANALYST_MAX_SOURCES",
            "max_cost_usd": "POLYANALYST_MAX_COST_USD",
            "max_duration_seconds": "POLYANALYST_MAX_DURATION_SECONDS",
        }
        for field_name, environment_name in mapping.items():
            if environment_name in os.environ:
                values[field_name] = os.environ[environment_name]
        settings = cls.model_validate(values)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        return settings
