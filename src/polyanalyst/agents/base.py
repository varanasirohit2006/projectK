"""Common agent contracts and result objects."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from polyanalyst.models import Contradiction, Finding, ResearchQuery


class SearchResult(BaseModel):
    """Provider-neutral result returned by a search tool."""

    title: str
    content: str
    url: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    source_type: str = "web"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchProvider(Protocol):
    """Interface implemented by web, MCP, or test search providers."""

    def search(self, query: ResearchQuery, limit: int) -> list[SearchResult]:
        """Return up to ``limit`` relevant results."""


class AgentOutput(BaseModel):
    """Normalized output exchanged through workflow state."""

    agent_name: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    finding: Finding | None = None
    contradictions: list[Contradiction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


EventEmitter = Callable[[str, str, str | None, dict[str, Any]], None]
