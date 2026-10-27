from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.models import EvidenceItem, ReportClaim, ResearchQuery, Source, SourceType


def test_evidence_store_preserves_claim_links(tmp_path) -> None:
    path = tmp_path / "evidence.db"
    with SQLiteEvidenceStore(path) as store:
        source = Source(
            title="A source",
            source_type=SourceType.DOCUMENT,
            document_id="doc-1",
            content_hash="hash-1",
        )
        evidence = EvidenceItem(
            run_id="run-1",
            claim="A measurable finding",
            excerpt="The relevant passage",
            source_id=source.source_id,
        )
        claim = ReportClaim(text="A measurable finding", evidence_ids=[evidence.evidence_id])
        store.add_source(source, run_id="run-1")
        store.add_evidence(evidence)
        store.add_claim(claim, run_id="run-1")

        assert store.get_evidence(evidence.evidence_id) == evidence
        assert store.evidence_for_claim(claim.claim_id) == [evidence]


def test_run_repository_saves_events_and_checkpoints(tmp_path) -> None:
    path = tmp_path / "runs.db"
    with RunRepository(path) as repository:
        run = repository.create_run(ResearchQuery(question="What changed in the market?"))
        repository.save_checkpoint(run.run_id, {"step": "plan", "task_count": 2})
        assert repository.load_checkpoint(run.run_id) == {"step": "plan", "task_count": 2}
        assert repository.get_run(run.run_id) == run
