from pathlib import Path
from xml.etree import ElementTree

import pytest

from polyanalyst.models import EvidenceItem, ResearchQuery, Source, SourceType
from polyanalyst.reporting.drafting import DraftReport
from polyanalyst.reporting.export import export_markdown, export_pdf
from polyanalyst.reporting.visuals import ReportVisualGenerator, image_citation


def make_evidence() -> tuple[list[EvidenceItem], dict[str, Source]]:
    source = Source(
        source_id="source-1",
        title="Operations report",
        publisher="Example publisher",
        source_type=SourceType.WEB,
        url="https://example.com/operations",
        content_hash="hash-1",
    )
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        claim="Supplier lead times increased.",
        excerpt="Supplier lead times increased.",
        source_id=source.source_id,
        confidence=0.8,
        quality_score=0.9,
        freshness_score=0.7,
    )
    return [evidence], {source.source_id: source}


def test_visual_generator_creates_cited_svg_assets(tmp_path: Path) -> None:
    evidence, sources = make_evidence()
    generator = ReportVisualGenerator(tmp_path / "runs")

    images = generator.generate(
        "run-1",
        ResearchQuery(question="Analyze operations"),
        evidence,
        sources,
    )

    assert len(images) == 4
    assert all(image.evidence_ids == ["evidence-1"] for image in images)
    assert all(Path(image.path).is_file() for image in images)
    assert all("[E1]" in image_citation(image, {"evidence-1": "E1"}) for image in images)
    for image in images:
        ElementTree.parse(image.path)


def test_external_image_requires_attribution(tmp_path: Path) -> None:
    image_path = tmp_path / "external.svg"
    image_path.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    generator = ReportVisualGenerator(tmp_path / "runs")

    with pytest.raises(ValueError, match="source URL"):
        generator.register_external_image(
            "run-1",
            image_path,
            title="External figure",
            alt_text="External figure",
            source_url="",
            source_title="Example",
            attribution="Example",
        )


def test_markdown_export_copies_report_images(tmp_path: Path) -> None:
    evidence, sources = make_evidence()
    images = ReportVisualGenerator(tmp_path / "runs").generate(
        "run-1",
        ResearchQuery(question="Analyze operations"),
        evidence,
        sources,
    )
    destination = tmp_path / "export" / "report.md"
    report = DraftReport(
        title="Operations",
        markdown="![Evidence summary](images/run-summary.svg)\n",
        images=images,
    )

    export_markdown(report, destination)

    assert destination.is_file()
    assert (destination.parent / "images" / "run-summary.svg").is_file()


def test_pdf_export_keeps_image_citations(tmp_path: Path) -> None:
    evidence, sources = make_evidence()
    images = ReportVisualGenerator(tmp_path / "runs").generate(
        "run-1",
        ResearchQuery(question="Analyze operations"),
        evidence,
        sources,
    )
    destination = tmp_path / "export" / "report.pdf"
    report = DraftReport(
        title="Operations",
        markdown=(
            "# Operations\n\n"
            "## Visual evidence and image citations\n\n"
            "![Evidence summary](images/run-summary.svg)\n"
        ),
        citation_labels={"evidence-1": "E1"},
        images=images,
    )

    export_pdf(report, destination)

    assert destination.is_file()
    assert destination.stat().st_size > 0
