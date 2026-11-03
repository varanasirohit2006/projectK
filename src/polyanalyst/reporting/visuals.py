"""Evidence-derived report image generation with explicit provenance.

The default visuals are deterministic SVG files generated from structured run
data. They do not copy images from the web or invent unsupported statistics.
External images can be registered only with a source URL and attribution.
"""

# SVG template lines are intentionally readable as single markup fragments.
# ruff: noqa: E501

from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path

from polyanalyst.models import (
    EvidenceItem,
    ImageSourceKind,
    ReportImage,
    ResearchQuery,
    Source,
)


class ReportVisualGenerator:
    """Create cited SVG figures for a research run."""

    def __init__(self, output_root: str | Path = "data/runs") -> None:
        self.output_root = Path(output_root)

    def generate(
        self,
        run_id: str,
        query: ResearchQuery,
        evidence: list[EvidenceItem],
        sources: dict[str, Source | None],
    ) -> list[ReportImage]:
        """Generate a summary, quality chart, and source-mix chart."""

        output_dir = self.output_root / run_id / "images"
        output_dir.mkdir(parents=True, exist_ok=True)
        evidence_ids = [item.evidence_id for item in evidence]
        images = [
            self._write(
                run_id,
                output_dir,
                "evidence-lineage.svg",
                "Evidence lineage",
                "Lineage from source records to cited evidence items.",
                self._lineage_svg(evidence, sources),
                evidence_ids,
            ),
            self._write(
                run_id,
                output_dir,
                "run-summary.svg",
                "Run evidence summary",
                "Summary of the question, evidence count, and confidence metrics.",
                self._summary_svg(query, evidence),
                evidence_ids,
            )
        ]
        if evidence:
            images.extend(
                [
                    self._write(
                        run_id,
                        output_dir,
                        "evidence-quality.svg",
                        "Evidence quality profile",
                        "Quality, freshness, and confidence for each cited evidence item.",
                        self._quality_svg(evidence, sources),
                        evidence_ids,
                    ),
                    self._write(
                        run_id,
                        output_dir,
                        "source-mix.svg",
                        "Source mix",
                        "Distribution of evidence by source type with citation labels.",
                        self._source_mix_svg(evidence, sources),
                        evidence_ids,
                    ),
                ]
            )
        return images

    def register_external_image(
        self,
        run_id: str,
        path: str | Path,
        *,
        title: str,
        alt_text: str,
        source_url: str,
        source_title: str,
        attribution: str,
        evidence_ids: list[str] | None = None,
    ) -> ReportImage:
        """Register a local image only when its external attribution is known."""

        if not source_url.strip():
            raise ValueError("External images require a source URL")
        if not attribution.strip():
            raise ValueError("External images require attribution")
        image_path = Path(path)
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        return ReportImage(
            run_id=run_id,
            title=title,
            alt_text=alt_text,
            path=str(image_path),
            report_path=f"images/{image_path.name}",
            source_kind=ImageSourceKind.EXTERNAL,
            evidence_ids=evidence_ids or [],
            source_url=source_url,
            source_title=source_title,
            attribution=attribution,
            generated_by=None,
        )

    def _write(
        self,
        run_id: str,
        output_dir: Path,
        filename: str,
        title: str,
        alt_text: str,
        svg: str,
        evidence_ids: list[str],
    ) -> ReportImage:
        path = output_dir / filename
        path.write_text(svg, encoding="utf-8")
        return ReportImage(
            run_id=run_id,
            title=title,
            alt_text=alt_text,
            path=str(path),
            report_path=f"images/{filename}",
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _lineage_svg(evidence: list[EvidenceItem], sources: dict[str, Source | None]) -> str:
        rows = evidence[:6]
        body = []
        for index, item in enumerate(rows, start=1):
            y = 115 + (index - 1) * 42
            source = sources.get(item.source_id)
            source_title = escape((source.title if source else item.source_id)[:46])
            body.append(
                f'<rect x="55" y="{y - 25}" width="220" height="30" rx="10" fill="#2563eb"/>'
                f'<text x="165" y="{y - 5}" text-anchor="middle" fill="white" '
                f'font-family="Arial" font-size="14">[{f"E{index}"}] {source_title}</text>'
                f'<path d="M285 {y - 10} H405" stroke="#64748b" stroke-width="3"/>'
                f'<rect x="420" y="{y - 25}" width="300" height="30" rx="10" fill="#0f766e"/>'
                f'<text x="570" y="{y - 5}" text-anchor="middle" fill="white" '
                f'font-family="Arial" font-size="14">Evidence {index}: cited excerpt</text>'
            )
        height = max(240, 145 + len(rows) * 42)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}">
<rect width="800" height="{height}" rx="24" fill="#f8fafc"/>
<text x="55" y="58" fill="#0f172a" font-family="Arial" font-size="28" font-weight="700">Evidence lineage</text>
<text x="55" y="84" fill="#64748b" font-family="Arial" font-size="14">Source records become traceable evidence items used by the report.</text>
{''.join(body)}
</svg>"""

    @staticmethod
    def _summary_svg(query: ResearchQuery, evidence: list[EvidenceItem]) -> str:
        count = len(evidence)
        average = sum(item.confidence for item in evidence) / count if evidence else 0
        quality = sum(item.quality_score for item in evidence) / count if evidence else 0
        question = escape(query.question[:90])
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="390" viewBox="0 0 1100 390">
<rect width="1100" height="390" rx="24" fill="#0f172a"/>
<text x="55" y="58" fill="#f8fafc" font-family="Arial" font-size="28" font-weight="700">Run evidence summary</text>
<text x="55" y="94" fill="#bfdbfe" font-family="Arial" font-size="16">{question}</text>
<g font-family="Arial">
<rect x="55" y="145" width="290" height="150" rx="18" fill="#2563eb"/><text x="85" y="190" fill="#dbeafe" font-size="16">EVIDENCE ITEMS</text><text x="85" y="250" fill="white" font-size="52" font-weight="700">{count}</text>
<rect x="405" y="145" width="290" height="150" rx="18" fill="#0f766e"/><text x="435" y="190" fill="#ccfbf1" font-size="16">AVERAGE QUALITY</text><text x="435" y="250" fill="white" font-size="52" font-weight="700">{quality:.0%}</text>
<rect x="755" y="145" width="290" height="150" rx="18" fill="#7c3aed"/><text x="785" y="190" fill="#ede9fe" font-size="16">AVERAGE CONFIDENCE</text><text x="785" y="250" fill="white" font-size="52" font-weight="700">{average:.0%}</text>
</g><text x="55" y="350" fill="#93c5fd" font-family="Arial" font-size="14">Generated from this run's structured evidence; no external image was copied.</text>
</svg>"""

    @staticmethod
    def _quality_svg(evidence: list[EvidenceItem], sources: dict[str, Source | None]) -> str:
        rows = evidence[:10]
        height = 150 + len(rows) * 42
        body = []
        for index, item in enumerate(rows, start=1):
            y = 125 + (index - 1) * 42
            label = f"E{index}"
            source = sources.get(item.source_id)
            title = escape((source.title if source else item.source_id)[:36])
            body.append(
                f'<text x="52" y="{y}" fill="#0f172a" font-family="Arial" font-size="14">'
                f'<tspan font-weight="700">[{label}]</tspan> {title}</text>'
                f'<rect x="390" y="{y - 15}" width="250" height="18" rx="9" fill="#e2e8f0"/>'
                f'<rect x="390" y="{y - 15}" width="{250 * item.quality_score:.1f}" height="18" rx="9" fill="#0f766e"/>'
                f'<rect x="670" y="{y - 15}" width="250" height="18" rx="9" fill="#e2e8f0"/>'
                f'<rect x="670" y="{y - 15}" width="{250 * item.confidence:.1f}" height="18" rx="9" fill="#7c3aed"/>'
                f'<text x="945" y="{y}" fill="#334155" font-family="Arial" font-size="13">'
                f"quality {item.quality_score:.0%} · confidence {item.confidence:.0%}</text>"
            )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" viewBox="0 0 1100 {height}">
<rect width="1100" height="{height}" rx="24" fill="#f8fafc"/>
<text x="52" y="58" fill="#0f172a" font-family="Arial" font-size="28" font-weight="700">Evidence quality profile</text>
<text x="52" y="88" fill="#64748b" font-family="Arial" font-size="14">Green = quality · purple = confidence · labels resolve to the report evidence appendix</text>
{''.join(body)}
</svg>"""

    @staticmethod
    def _source_mix_svg(evidence: list[EvidenceItem], sources: dict[str, Source | None]) -> str:
        counts = Counter((sources.get(item.source_id).source_type.value if sources.get(item.source_id) else "unknown") for item in evidence)
        entries = list(counts.items())
        body = []
        for index, (source_type, count) in enumerate(entries):
            y = 145 + index * 48
            width = min(600, count * 120)
            body.append(
                f'<text x="70" y="{y}" fill="#0f172a" font-family="Arial" font-size="17">{escape(source_type)}</text>'
                f'<rect x="260" y="{y - 19}" width="600" height="24" rx="12" fill="#e2e8f0"/>'
                f'<rect x="260" y="{y - 19}" width="{width}" height="24" rx="12" fill="#2563eb"/>'
                f'<text x="885" y="{y}" fill="#334155" font-family="Arial" font-size="15">{count} cited item(s)</text>'
            )
        citations = ", ".join(f"E{index}" for index, _ in enumerate(evidence, start=1))
        height = max(300, 190 + len(entries) * 48)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="{height}" viewBox="0 0 1100 {height}">
<rect width="1100" height="{height}" rx="24" fill="#eff6ff"/>
<text x="70" y="60" fill="#0f172a" font-family="Arial" font-size="28" font-weight="700">Source mix</text>
{''.join(body)}
<text x="70" y="{height - 45}" fill="#475569" font-family="Arial" font-size="14">Citations represented: {escape(citations) or 'none'}</text>
</svg>"""


def image_citation(image: ReportImage, citation_labels: dict[str, str] | None = None) -> str:
    """Return the attribution line shown below a report figure."""

    labels = citation_labels or {}
    evidence = ", ".join(f"[{labels.get(item, item)}]" for item in image.evidence_ids)
    if image.source_kind == ImageSourceKind.EXTERNAL:
        source = image.source_title or image.source_url or "external source"
        return f"Image source: [{source}]({image.source_url}); attribution: {image.attribution}."
    if evidence:
        return (
            f"Generated by PolyAnalyst from cited evidence {evidence}; "
            "no external image was copied."
        )
    return "Generated by PolyAnalyst from run metadata; no external image was copied."
