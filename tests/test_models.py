from datetime import UTC, datetime

from polyanalyst.models import (
    EvidenceItem,
    ResearchQuery,
    ResearchTask,
    Source,
    SourceType,
    TaskKind,
)


def test_query_normalizes_whitespace() -> None:
    query = ResearchQuery(question="  What   are supply-chain risks? ")
    assert query.question == "What are supply-chain risks?"


def test_domain_models_round_trip_json() -> None:
    source = Source(
        title="Example source",
        source_type=SourceType.WEB,
        url="https://example.com/report",
        content_hash="abc123",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    evidence = EvidenceItem(
        claim="Lead times increased.",
        excerpt="The report records a longer lead time.",
        source_id=source.source_id,
    )
    task = ResearchTask(
        kind=TaskKind.RESEARCH,
        title="Find current sources",
        description="Search trusted sources",
        agent_name="research",
        output_refs=[evidence.evidence_id],
    )

    restored = ResearchTask.model_validate_json(task.model_dump_json())
    assert restored.task_id == task.task_id
    assert evidence.source_id == source.source_id
