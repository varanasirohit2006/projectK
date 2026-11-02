"""Presentation helpers shared by Markdown, Streamlit, and exports."""

from __future__ import annotations

from dataclasses import dataclass

from polyanalyst.models import EvidenceItem, Source


@dataclass(frozen=True)
class CitationMap:
    """Map opaque evidence IDs to readable report labels."""

    labels: dict[str, str]

    @classmethod
    def from_evidence(cls, evidence: list[EvidenceItem]) -> CitationMap:
        return cls(
            labels={item.evidence_id: f"E{index}" for index, item in enumerate(evidence, start=1)}
        )

    def label(self, evidence_id: str) -> str:
        return self.labels.get(evidence_id, evidence_id)


def source_title(source: Source | None, source_id: str) -> str:
    return source.title if source else f"Source {source_id}"


def source_reference(source: Source | None, source_id: str) -> str:
    """Return a compact human-readable source reference."""

    if source is None:
        return f"`{source_id}`"
    reference = source.title
    if source.publisher:
        reference += f" — {source.publisher}"
    if source.url:
        reference += f" — {source.url}"
    elif source.document_id:
        reference += f" — document: {source.document_id}"
    return reference


def score_badge(score: float) -> str:
    return f"{score:.0%}"


def asset_image(name: str, alt: str) -> str:
    """Return a relative image reference for exported reports."""

    return f"![{alt}](../docs/assets/{name})"
