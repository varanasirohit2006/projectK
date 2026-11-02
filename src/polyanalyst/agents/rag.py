"""Private-document retrieval agent."""

from __future__ import annotations

import hashlib

from polyanalyst.agents.base import AgentOutput
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.models import EvidenceItem, Finding, ResearchQuery, Source, SourceType
from polyanalyst.security.guardrails import inspect_untrusted_text


class RAGAgent:
    """Retrieve document passages and turn them into provenance-rich evidence."""

    def __init__(self, document_store: InMemoryDocumentStore) -> None:
        self.document_store = document_store

    def run(
        self,
        query: ResearchQuery,
        run_id: str,
        task_id: str,
        store: SQLiteEvidenceStore,
    ) -> AgentOutput:
        matches = (
            self.document_store.search(
                query.question,
                limit=query.max_sources,
                collection_ids=query.collection_ids,
            )
            if query.collection_ids
            else []
        )
        evidence_ids: list[str] = []
        for chunk, score in matches:
            guardrail = inspect_untrusted_text(chunk.text)
            content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            source = Source(
                document_id=chunk.document_id,
                title=chunk.title,
                publisher=chunk.metadata.get("publisher"),
                source_type=SourceType.DOCUMENT,
                content_hash=content_hash,
                quality_score=0.8,
                freshness_score=0.7,
            )
            store.add_source(source, run_id=run_id)
            evidence = EvidenceItem(
                run_id=run_id,
                claim=chunk.text,
                excerpt=chunk.text,
                source_id=source.source_id,
                location=f"characters {chunk.start_offset}-{chunk.end_offset}",
                confidence=min(0.55 + score * 0.4, 0.95),
                quality_score=source.quality_score,
                freshness_score=source.freshness_score,
                task_id=task_id,
                agent_id="rag",
                metadata={
                    "collection_id": chunk.collection_id,
                    **chunk.metadata,
                    "untrusted_content": True,
                    "prompt_injection_flagged": guardrail.flagged,
                    "prompt_injection_signals": guardrail.signals,
                },
            )
            store.add_evidence(evidence)
            evidence_ids.append(evidence.evidence_id)

        summary = f"RAG agent retrieved {len(evidence_ids)} private passage(s)."
        finding = Finding(
            run_id=run_id,
            agent_name="rag",
            summary=summary,
            evidence_ids=evidence_ids,
            metrics={"retrieval_count": float(len(evidence_ids))},
        )
        return AgentOutput(
            agent_name="rag",
            summary=summary,
            evidence_ids=evidence_ids,
            finding=finding,
            metadata={"retrieval_count": len(evidence_ids)},
        )
