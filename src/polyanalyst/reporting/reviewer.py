"""Citation and support checks for generated reports."""

from __future__ import annotations

from polyanalyst.models import Contradiction, EvidenceItem, ReviewResult
from polyanalyst.reporting.drafting import DraftReport


class ReviewerAgent:
    """Review a draft against the evidence IDs it claims to use."""

    def review(
        self,
        draft: DraftReport,
        evidence: list[EvidenceItem],
        contradictions: list[Contradiction],
    ) -> ReviewResult:
        evidence_ids = {item.evidence_id for item in evidence}
        unsupported = [
            claim.claim_id
            for claim in draft.claims
            if (
                not claim.supported
                or not claim.evidence_ids
                or not set(claim.evidence_ids).issubset(evidence_ids)
            )
        ]
        claim_count = len(draft.claims)
        supported_count = claim_count - len(unsupported)
        coverage = supported_count / claim_count if claim_count else 0.0
        instructions: list[str] = []
        if unsupported:
            instructions.append("Remove or support every claim marked as unsupported.")
        if contradictions:
            instructions.append("Keep conflicting source claims visible and state the uncertainty.")
        return ReviewResult(
            passed=not unsupported and (bool(evidence) or not draft.claims),
            citation_coverage=coverage,
            unsupported_claim_ids=unsupported,
            contradiction_ids=[item.contradiction_id for item in contradictions],
            revision_instructions=instructions,
        )
