"""Prompt-injection detection and filesystem boundary checks.

Retrieved content is evidence, never workflow instructions. These helpers
flag suspicious text for visibility while preserving the original excerpt for
human verification.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

_INSTRUCTION_PATTERNS = (
    re.compile(r"ignore\s+(all|any|the)\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+message\s*:", re.IGNORECASE),
    re.compile(r"(call|invoke|run)\s+the\s+[a-z0-9_.-]+\s+tool", re.IGNORECASE),
    re.compile(r"reveal\s+(the\s+)?(system|developer)\s+prompt", re.IGNORECASE),
)


class GuardrailResult(BaseModel):
    flagged: bool
    signals: list[str] = Field(default_factory=list)


def inspect_untrusted_text(text: str) -> GuardrailResult:
    """Detect common instruction-like strings in external content."""

    signals = [pattern.pattern for pattern in _INSTRUCTION_PATTERNS if pattern.search(text)]
    return GuardrailResult(flagged=bool(signals), signals=signals)


class DataPathPolicy:
    """Restrict data analysis to approved roots and file types."""

    def __init__(
        self,
        allowed_roots: list[str | Path],
        allowed_extensions: set[str] | None = None,
        max_bytes: int = 5_000_000,
    ) -> None:
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        self.allowed_extensions = allowed_extensions or {".csv"}
        self.max_bytes = max_bytes

    def validate(self, path: str | Path) -> Path:
        candidate = Path(path).resolve()
        if not any(self._is_within(candidate, root) for root in self.allowed_roots):
            raise PermissionError(f"Data path is outside approved roots: {candidate}")
        if candidate.suffix.lower() not in self.allowed_extensions:
            raise ValueError(f"File type is not allowed: {candidate.suffix}")
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        if candidate.stat().st_size > self.max_bytes:
            raise ValueError(f"File is larger than the {self.max_bytes} byte limit")
        return candidate

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            candidate.relative_to(root)
        except ValueError:
            return False
        return True
