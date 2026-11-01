"""Web-search tool adapters for the research agent."""

from __future__ import annotations

from polyanalyst.agents.base import SearchProvider, SearchResult
from polyanalyst.models import ResearchQuery
from polyanalyst.tools.mcp_client import MCPClient, ToolDefinition

WEB_SEARCH_TOOL = ToolDefinition(
    name="web.search",
    description="Search approved external sources for current research evidence.",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
    },
)


class MCPWebSearchProvider(SearchProvider):
    """Adapt an MCP web-search tool to the research-agent contract."""

    def __init__(self, client: MCPClient, tool_name: str = WEB_SEARCH_TOOL.name) -> None:
        self.client = client
        self.tool_name = tool_name

    def search(self, query: ResearchQuery, limit: int) -> list[SearchResult]:
        response = self.client.call(
            self.tool_name,
            {"query": query.question, "limit": limit},
        )
        if not isinstance(response, list):
            raise TypeError("web.search must return a list")
        return [SearchResult.model_validate(item) for item in response[:limit]]


def register_web_search(client: MCPClient, provider: SearchProvider) -> None:
    """Expose a provider through a local MCP-style client."""

    def handler(arguments: dict[str, object]) -> list[dict[str, object]]:
        query = ResearchQuery(question=str(arguments.get("query", "")))
        limit = int(arguments.get("limit", 10))
        return [result.model_dump(mode="json") for result in provider.search(query, limit)]

    client.register(WEB_SEARCH_TOOL, handler)
