from pathlib import Path

import pytest

from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.graph.workflow import ResearchWorkflow
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.models import ResearchQuery, RiskLevel, RunStatus


def make_workflow(tmp_path: Path, document_store: InMemoryDocumentStore | None = None):
    database = tmp_path / "workflow.db"
    evidence = SQLiteEvidenceStore(database)
    runs = RunRepository(database)
    workflow = ResearchWorkflow(evidence, runs, document_store=document_store)
    return workflow, evidence, runs


def test_workflow_exposes_plan_before_execution(tmp_path: Path) -> None:
    workflow, evidence, runs = make_workflow(tmp_path)
    try:
        result = workflow.run(ResearchQuery(question="Analyze operational resilience risks"))
        assert result.status == RunStatus.WAITING_FOR_PLAN_APPROVAL
        assert result.state.plan is not None
        assert result.state.plan.approved is False
        assert result.state.plan.tasks[-1].kind.value == "review"
    finally:
        evidence.close()
        runs.close()


def test_workflow_runs_research_rag_data_and_review(tmp_path: Path) -> None:
    documents = InMemoryDocumentStore()
    documents.add_text(
        "memo-1",
        "Operations memo",
        "Supplier lead times and inventory visibility affect supply chain resilience.",
        collection_id="operations",
    )
    csv_path = tmp_path / "signals.csv"
    csv_path.write_text("month,lead_time\nJan,4\nFeb,6\n", encoding="utf-8")
    workflow, evidence, runs = make_workflow(tmp_path, documents)
    try:
        result = workflow.run(
            ResearchQuery(
                question="Analyze supply chain resilience and operational risk",
                collection_ids=["operations"],
                data_paths=[str(csv_path)],
            ),
            approve_plan=True,
        )
        assert result.status == RunStatus.COMPLETED
        assert result.state.review is not None
        assert result.state.review.passed is True
        assert len(result.state.evidence_ids) >= 3
        assert "Evidence appendix" in (result.state.report_markdown or "")
        assert len(runs.list_events(result.run_id)) >= 10
    finally:
        evidence.close()
        runs.close()


def test_high_risk_run_pauses_and_resumes_after_approval(tmp_path: Path) -> None:
    workflow, evidence, runs = make_workflow(tmp_path)
    try:
        result = workflow.run(
            ResearchQuery(
                question="Recommend a financial investment strategy",
                risk_level=RiskLevel.HIGH,
            ),
            approve_plan=True,
        )
        assert result.status == RunStatus.WAITING_FOR_HUMAN_APPROVAL
        assert result.state.evidence_ids == []
        resumed = workflow.resume(result.run_id, human_approval=True)
        assert resumed.status == RunStatus.COMPLETED
        with pytest.raises(ValueError, match="terminal"):
            workflow.resume(result.run_id, human_approval=True)
    finally:
        evidence.close()
        runs.close()
