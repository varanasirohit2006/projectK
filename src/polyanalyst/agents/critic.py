"""Risk synthesis and lightweight contradiction detection."""

from __future__ import annotations

import re

from polyanalyst.agents.base import AgentOutput
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.models import Contradiction, EvidenceItem, Finding, ResearchQuery

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "because",
    "from",
    "that",
    "the",
    "their",
    "this",
    "with",
}
_OPPOSING_GROUPS = (
    ({"increase", "increased", "increasing", "higher", "growth", "improve", "improved"},
     {"decrease", "decreased", "decreasing", "lower", "decline", "declined", "worsen"}),
    ({"reduce", "reduced", "reduction", "less"}, {"raise", "raised", "more", "increase"}),
)


class RiskCriticAgent:
    """Synthesize evidence quality, risks, and disagreements."""

    def run(
        self,
        query: ResearchQuery,
        run_id: str,
        store: SQLiteEvidenceStore,
    ) -> AgentOutput:
        evidence = store.list_unique_evidence(run_id)
        contradictions = self.detect_contradictions(evidence)
        risk_items = [
            item
            for item in evidence
            if any(
                term in item.claim.lower()
                for term in ("risk", "shortage", "disruption", "decline")
            )
        ]
        average_quality = (
            sum(item.quality_score for item in evidence) / len(evidence) if evidence else 0.0
        )
        summary = (
            f"Critic reviewed {len(evidence)} evidence item(s), identified {len(risk_items)} "
            f"risk signal(s), and found {len(contradictions)} contradiction(s)."
        )
        finding = Finding(
            run_id=run_id,
            agent_name="critic",
            summary=summary,
            evidence_ids=[item.evidence_id for item in evidence],
            metrics={
                "average_quality": average_quality,
                "contradiction_count": float(len(contradictions)),
            },
        )
        return AgentOutput(
            agent_name="critic",
            summary=summary,
            evidence_ids=[item.evidence_id for item in evidence],
            finding=finding,
            contradictions=contradictions,
            metadata={
                "risk_evidence_ids": [item.evidence_id for item in risk_items],
                "query": query.question,
            },
        )

    @classmethod
    def detect_contradictions(cls, evidence: list[EvidenceItem]) -> list[Contradiction]:
        """Find explicit opposing directional claims sharing a subject token."""

        contradictions: list[Contradiction] = []
        for index, first in enumerate(evidence):
            first_tokens = cls._tokens(first.claim)
            for second in evidence[index + 1 :]:
                second_tokens = cls._tokens(second.claim)
                shared = first_tokens.intersection(second_tokens)
                if not shared or not cls._has_opposing_terms(first_tokens, second_tokens):
                    continue
                contradictions.append(
                    Contradiction(
                        claim_a=first.claim,
                        claim_b=second.claim,
                        evidence_ids=[first.evidence_id, second.evidence_id],
                        resolution=(
                            "Preserve both claims and explain the disagreement in the report."
                        ),
                        confidence=0.65,
                    )
                )
        return contradictions

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(_TOKEN_PATTERN.findall(text.lower())) - _STOPWORDS

    @staticmethod
    def _has_opposing_terms(first: set[str], second: set[str]) -> bool:
        return any(
            (first.intersection(left) and second.intersection(right))
            or (first.intersection(right) and second.intersection(left))
            for left, right in _OPPOSING_GROUPS
        )
