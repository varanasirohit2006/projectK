"""Safe report export helpers."""

from __future__ import annotations

from pathlib import Path

from polyanalyst.reporting.drafting import DraftReport


def export_markdown(report: DraftReport, destination: str | Path) -> Path:
    """Write a report as UTF-8 Markdown and return its path."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.markdown, encoding="utf-8")
    return path
