"""Simple deterministic text chunking with source locations."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[tuple[str, int, int]]:
    """Split text into character chunks and return text plus start/end offsets."""

    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    normalized = " ".join(text.split())
    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append((normalized[start:end], start, end))
        if end == len(normalized):
            break
        start = end - overlap
    return chunks
