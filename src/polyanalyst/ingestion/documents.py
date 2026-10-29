"""In-memory document collection used by the RAG agent.

The interface is deliberately small so ChromaDB can replace this store as an
optional adapter without changing the workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from polyanalyst.ingestion.chunking import chunk_text

_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class DocumentChunk:
    document_id: str
    title: str
    text: str
    start_offset: int
    end_offset: int
    collection_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class InMemoryDocumentStore:
    """Store document chunks and rank them by lexical query overlap."""

    def __init__(self) -> None:
        self._chunks: list[DocumentChunk] = []

    def add_text(
        self,
        document_id: str,
        title: str,
        text: str,
        *,
        collection_id: str | None = None,
        metadata: dict[str, str] | None = None,
        chunk_size: int = 800,
        overlap: int = 100,
    ) -> int:
        """Chunk and add a document, returning the number of chunks created."""

        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        self._chunks = [chunk for chunk in self._chunks if chunk.document_id != document_id]
        self._chunks.extend(
            DocumentChunk(
                document_id=document_id,
                title=title,
                text=chunk,
                start_offset=start,
                end_offset=end,
                collection_id=collection_id,
                metadata=metadata or {},
            )
            for chunk, start, end in chunks
        )
        return len(chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        collection_ids: list[str] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return the best matching chunks and normalized lexical scores."""

        query_tokens = set(_TOKEN_PATTERN.findall(query.lower()))
        if not query_tokens:
            return []
        allowed = set(collection_ids or [])
        ranked: list[tuple[DocumentChunk, float]] = []
        for chunk in self._chunks:
            if allowed and chunk.collection_id not in allowed:
                continue
            chunk_tokens = set(_TOKEN_PATTERN.findall(chunk.text.lower()))
            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap:
                ranked.append((chunk, min(overlap / len(query_tokens), 1.0)))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:limit]

    def count(self) -> int:
        return len(self._chunks)
