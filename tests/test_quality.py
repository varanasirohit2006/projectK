from polyanalyst.evidence.quality import deduplicate_evidence
from polyanalyst.models import EvidenceItem


def test_quality_policy_keeps_strongest_duplicate() -> None:
    weaker = EvidenceItem(
        evidence_id="weak",
        claim="Lead times increased.",
        excerpt="Lead times increased.",
        source_id="s1",
        confidence=0.4,
        quality_score=0.4,
    )
    stronger = weaker.model_copy(
        update={"evidence_id": "strong", "source_id": "s2", "confidence": 0.9}
    )

    assert [item.evidence_id for item in deduplicate_evidence([weaker, stronger])] == ["strong"]
