"""Benchmark cases and run-level evaluation."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from polyanalyst.evaluation.metrics import (
    EvaluationSummary,
    answer_correctness,
    citation_coverage,
    faithfulness,
    recall_at_k,
)
from polyanalyst.graph.state import WorkflowResult
from polyanalyst.models import EvidenceItem, PolyModel, ReportClaim


class BenchmarkCase(PolyModel):
    case_id: str
    question: str
    reference_answer: str
    relevant_evidence_ids: list[str] = Field(default_factory=list)


class BenchmarkRunner:
    """Evaluate a completed run against a verified benchmark case."""

    def evaluate(
        self,
        case: BenchmarkCase,
        result: WorkflowResult,
        evidence: Iterable[EvidenceItem],
    ) -> EvaluationSummary:
        evidence_list = list(evidence)
        claims: list[ReportClaim] = result.state.report_claims
        report = result.state.report_markdown or ""
        metrics = {
            "recall_at_3": recall_at_k(result.state.evidence_ids, case.relevant_evidence_ids, 3),
            "faithfulness": faithfulness(claims, evidence_list),
            "citation_coverage": citation_coverage(claims, evidence_list),
            "answer_correctness": answer_correctness(report, case.reference_answer),
        }
        return EvaluationSummary(
            metrics=metrics,
            details={"case_id": case.case_id, "run_id": result.run_id},
        )
