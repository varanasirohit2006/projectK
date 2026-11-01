"""Optional ChromaDB implementation of the document-store contract."""

from __future__ import annotations

from pathlib import Path

from polyanalyst.ingestion.chunking import chunk_text
from polyanalyst.ingestion.documents import DocumentChunk


class ChromaDocumentStore:
    """Persist document chunks in ChromaDB when the optional extra is installed."""

    def __init__(
        self,
        path: str | Path = "data/chroma",
        collection_name: str = "documents",
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install polyanalyst[vector] to use ChromaDB") from exc
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(collection_name)

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
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        ids = [f"{document_id}:{index}" for index in range(len(chunks))]
        self._collection.upsert(
            ids=ids,
            documents=[chunk[0] for chunk in chunks],
            metadatas=[
                {
                    "document_id": document_id,
                    "title": title,
                    "collection_id": collection_id or "",
                    "start_offset": chunk[1],
                    "end_offset": chunk[2],
                    **(metadata or {}),
                }
                for chunk in chunks
            ],
        )
        return len(chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        collection_ids: list[str] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        where = None
        if collection_ids:
            where = {"collection_id": {"$in": collection_ids}}
        response = self._collection.query(query_texts=[query], n_results=limit, where=where)
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        matches: list[tuple[DocumentChunk, float]] = []
        for text, metadata, distance in zip(documents, metadatas, distances, strict=False):
            score = max(0.0, 1.0 - float(distance))
            matches.append(
                (
                    DocumentChunk(
                        document_id=str(metadata["document_id"]),
                        title=str(metadata["title"]),
                        text=text,
                        start_offset=int(metadata["start_offset"]),
                        end_offset=int(metadata["end_offset"]),
                        collection_id=str(metadata.get("collection_id") or "") or None,
                        metadata={
                            key: str(value)
                            for key, value in metadata.items()
                            if key
                            not in {
                                "document_id",
                                "title",
                                "collection_id",
                                "start_offset",
                                "end_offset",
                            }
                        },
                    ),
                    score,
                )
            )
        return matches
