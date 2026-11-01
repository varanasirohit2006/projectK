"""Small, inspectable quality metrics for research runs."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from pydantic import Field

from polyanalyst.models import EvidenceItem, PolyModel, ReportClaim

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")


class EvaluationSummary(PolyModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    details: dict[str, object] = Field(default_factory=dict)


def recall_at_k(retrieved_ids: Iterable[str], relevant_ids: Iterable[str], k: int = 3) -> float:
    """Return whether at least one relevant item appears in the first ``k``."""

    relevant = set(relevant_ids)
    if not relevant:
        return 1.0
    return 1.0 if relevant.intersection(list(retrieved_ids)[:k]) else 0.0


def citation_coverage(claims: Iterable[ReportClaim], evidence: Iterable[EvidenceItem]) -> float:
    """Measure the proportion of report claims linked to known evidence."""

    claim_list = list(claims)
    evidence_ids = {item.evidence_id for item in evidence}
    if not claim_list:
        return 1.0
    supported = sum(
        1
        for claim in claim_list
        if claim.supported and set(claim.evidence_ids).issubset(evidence_ids)
    )
    return supported / len(claim_list)


def faithfulness(claims: Iterable[ReportClaim], evidence: Iterable[EvidenceItem]) -> float:
    """Estimate claim support using linked evidence token overlap."""

    evidence_by_id = {item.evidence_id: item for item in evidence}
    claim_list = list(claims)
    if not claim_list:
        return 1.0
    scores: list[float] = []
    for claim in claim_list:
        claim_tokens = set(_tokens(claim.text))
        linked = [
            evidence_by_id[item_id]
            for item_id in claim.evidence_ids
            if item_id in evidence_by_id
        ]
        if not claim_tokens or not linked:
            scores.append(0.0)
            continue
        overlap = max(
            len(claim_tokens.intersection(_tokens(item.excerpt))) / len(claim_tokens)
            for item in linked
        )
        scores.append(min(overlap, 1.0))
    return sum(scores) / len(scores)


def answer_correctness(answer: str, reference_answer: str) -> float:
    """Token F1 between a generated answer and a verified reference."""

    answer_counts = Counter(_tokens(answer))
    reference_counts = Counter(_tokens(reference_answer))
    if not answer_counts or not reference_counts:
        return 1.0 if answer.strip().lower() == reference_answer.strip().lower() else 0.0
    overlap = sum((answer_counts & reference_counts).values())
    precision = overlap / sum(answer_counts.values())
    recall = overlap / sum(reference_counts.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())
