"""Safe report export helpers."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from shutil import copy2

from polyanalyst.reporting.drafting import DraftReport
from polyanalyst.reporting.visuals import image_citation


def export_markdown(report: DraftReport, destination: str | Path) -> Path:
    """Write a report as UTF-8 Markdown and return its path."""

    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    for image in report.images:
        source = Path(image.path)
        if not source.is_file():
            raise FileNotFoundError(f"Report image is missing: {source}")
        target = path.parent / image.report_path
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
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
    try:
        from svglib.svglib import svg2rlg
    except ImportError:  # pragma: no cover - optional dependency
        svg2rlg = None

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
    images_by_report_path = {image.report_path: image for image in report.images}
    image_pattern = re.compile(r"^!\[(?P<alt>.*?)\]\((?P<path>.*?)\)$")
    for line in report.markdown.splitlines():
        image_match = image_pattern.match(line)
        if image_match:
            image = images_by_report_path.get(image_match.group("path"))
            if image is not None:
                story.append(Paragraph(escape(image.title), styles["Heading2"]))
                source = Path(image.path)
                if svg2rlg is not None and source.is_file():
                    drawing = svg2rlg(str(source))
                    if drawing is not None:
                        story.append(drawing)
                story.append(
                    Paragraph(
                        escape(image_citation(image, report.citation_labels)),
                        styles["BodyText"],
                    )
                )
            continue
        if not line.strip():
            story.append(Spacer(1, 0.12 * inch))
            continue
        style = styles["Heading1"] if line.startswith("# ") else styles["BodyText"]
        text = escape(line.lstrip("# "))
        story.append(Paragraph(text, style))
    document.build(story)
    return path
