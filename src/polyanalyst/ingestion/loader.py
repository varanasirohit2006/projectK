"""Safe, small-file document loading helpers."""

from __future__ import annotations

from pathlib import Path

from polyanalyst.ingestion.documents import InMemoryDocumentStore


class DocumentLoader:
    """Load text-like files into a document store with a size limit."""

    def __init__(self, max_bytes: int = 5_000_000) -> None:
        self.max_bytes = max_bytes

    def load_file(
        self,
        path: str | Path,
        store: InMemoryDocumentStore,
        *,
        collection_id: str | None = None,
    ) -> int:
        file_path = Path(path)
        if file_path.stat().st_size > self.max_bytes:
            raise ValueError(f"Document is larger than the {self.max_bytes} byte limit")
        if file_path.suffix.lower() not in {".txt", ".md", ".csv", ".log"}:
            raise ValueError("Only text, Markdown, CSV, and log files are supported")
        text = file_path.read_text(encoding="utf-8")
        return store.add_text(
            document_id=str(file_path.resolve()),
            title=file_path.name,
            text=text,
            collection_id=collection_id,
        )
