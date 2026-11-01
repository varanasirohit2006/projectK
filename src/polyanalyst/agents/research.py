"""Research agent and offline/provider-neutral search implementations."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from polyanalyst.agents.base import AgentOutput, SearchProvider, SearchResult
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.models import EvidenceItem, Finding, ResearchQuery, Source, SourceType
from polyanalyst.security.guardrails import inspect_untrusted_text


class DemoSearchProvider:
    """Small deterministic catalog used for local demos and integration tests."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or [
            SearchResult(
                title="PolyAnalyst demo: resilient operations",
                url="demo://resilient-operations",
                publisher="PolyAnalyst Demo Library",
                content=(
                    "Organizations that diversify critical suppliers, monitor lead times, "
                    "and maintain contingency inventory generally reduce disruption exposure."
                ),
            ),
            SearchResult(
                title="PolyAnalyst demo: market signals",
                url="demo://market-signals",
                publisher="PolyAnalyst Demo Library",
                content=(
                    "Recent market signals show that demand visibility and transparent "
                    "supplier data improve the quality of operational decisions."
                ),
            ),
        ]

    def search(self, query: ResearchQuery, limit: int) -> list[SearchResult]:
        """Return deterministic results while retaining the user's query in metadata."""

        return [
            result.model_copy(update={"metadata": {**result.metadata, "query": query.question}})
            for result in self.results[:limit]
        ]


class ResearchAgent:
    """Collect citable web evidence through a ``SearchProvider``."""

    def __init__(self, provider: SearchProvider | None = None) -> None:
        self.provider = provider or DemoSearchProvider()

    def run(
        self,
        query: ResearchQuery,
        run_id: str,
        task_id: str,
        store: SQLiteEvidenceStore,
    ) -> AgentOutput:
        results = self.provider.search(query, query.max_sources)
        evidence_ids: list[str] = []
        for result in results:
            guardrail = inspect_untrusted_text(result.content)
            content_hash = hashlib.sha256(result.content.encode("utf-8")).hexdigest()
            source = Source(
                url=result.url,
                title=result.title,
                publisher=result.publisher,
                source_type=SourceType.WEB,
                content_hash=content_hash,
                quality_score=self._quality_score(result),
                freshness_score=self._freshness_score(result),
                published_at=self._parse_date(result.published_at),
            )
            store.add_source(source, run_id=run_id)
            evidence = EvidenceItem(
                run_id=run_id,
                claim=result.content,
                excerpt=result.content,
                source_id=source.source_id,
                confidence=0.75,
                quality_score=source.quality_score,
                freshness_score=source.freshness_score,
                task_id=task_id,
                agent_id="research",
                metadata={
                    **result.metadata,
                    "untrusted_content": True,
                    "prompt_injection_flagged": guardrail.flagged,
                    "prompt_injection_signals": guardrail.signals,
                },
            )
            store.add_evidence(evidence)
            evidence_ids.append(evidence.evidence_id)

        summary = f"Research agent collected {len(evidence_ids)} citable source(s)."
        finding = Finding(
            run_id=run_id,
            agent_name="research",
            summary=summary,
            evidence_ids=evidence_ids,
        )
        return AgentOutput(
            agent_name="research",
            summary=summary,
            evidence_ids=evidence_ids,
            finding=finding,
            metadata={"result_count": len(results)},
        )

    @staticmethod
    def _quality_score(result: SearchResult) -> float:
        score = 0.45
        if result.publisher:
            score += 0.2
        if result.url and result.url.startswith("https://"):
            score += 0.2
        if len(result.content) >= 80:
            score += 0.15
        return min(score, 1.0)

    @staticmethod
    def _freshness_score(result: SearchResult) -> float:
        published_at = ResearchAgent._parse_date(result.published_at)
        if published_at is None:
            return 0.5
        age_days = max((datetime.now(UTC) - published_at).days, 0)
        return max(0.1, 1.0 - min(age_days / 365, 0.9))

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
