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


def export_pdf(report: DraftReport, destination: str | Path) -> Path:
    """Export a readable text-based PDF using the optional ReportLab extra."""

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install polyanalyst[pdf] to export PDF reports") from exc

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    story = []
    for line in report.markdown.splitlines():
        if not line.strip():
            story.append(Spacer(1, 0.12 * inch))
            continue
        style = styles["Heading1"] if line.startswith("# ") else styles["BodyText"]
        text = line.lstrip("# ")
        story.append(Paragraph(text.replace("&", "&amp;"), style))
    document.build(story)
    return path
