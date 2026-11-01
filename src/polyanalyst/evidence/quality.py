"""Source-quality and duplicate-evidence policies."""

from __future__ import annotations

import re

from polyanalyst.models import EvidenceItem

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")


def normalized_claim(claim: str) -> str:
    """Normalize a claim for deterministic duplicate detection."""

    return " ".join(_TOKEN_PATTERN.findall(claim.lower()))


def deduplicate_evidence(evidence: list[EvidenceItem]) -> list[EvidenceItem]:
    """Keep the strongest item for each normalized claim."""

    selected: dict[str, EvidenceItem] = {}
    for item in evidence:
        key = normalized_claim(item.claim)
        current = selected.get(key)
        if current is None or _strength(item) > _strength(current):
            selected[key] = item
    return sorted(selected.values(), key=lambda item: item.created_at)


def _strength(item: EvidenceItem) -> float:
    return item.confidence * 0.5 + item.quality_score * 0.3 + item.freshness_score * 0.2
