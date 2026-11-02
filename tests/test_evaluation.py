from polyanalyst.evaluation.metrics import (
    answer_correctness,
    citation_coverage,
    faithfulness,
    recall_at_k,
)
from polyanalyst.models import EvidenceItem, ReportClaim


def test_evaluation_metrics_measure_retrieval_and_support() -> None:
    evidence = EvidenceItem(
        evidence_id="e1",
        claim="Lead times increased to six weeks.",
        excerpt="Lead times increased to six weeks.",
        source_id="s1",
    )
    claim = ReportClaim(
        text="Lead times increased to six weeks.", evidence_ids=["e1"], supported=True
    )

    assert recall_at_k(["e1", "e2"], ["e1"]) == 1.0
    assert recall_at_k(["e1", "other"], ["e1", "e2"]) == 0.5
    assert citation_coverage([claim], [evidence]) == 1.0
    assert faithfulness([claim], [evidence]) == 1.0
    assert answer_correctness("lead times increased", "lead times increased") == 1.0
