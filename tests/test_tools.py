import sqlite3
import time

import pytest

from polyanalyst.agents.research import DemoSearchProvider
from polyanalyst.models import ResearchQuery
from polyanalyst.security.guardrails import DataPathPolicy
from polyanalyst.tools.budgets import BudgetExceeded, BudgetTracker
from polyanalyst.tools.cache import JsonCache
from polyanalyst.tools.database import ReadOnlyDatabaseTool, UnsafeQueryError
from polyanalyst.tools.mcp_client import MCPClient, MCPToolError, ToolDefinition
from polyanalyst.tools.web_search import MCPWebSearchProvider, register_web_search


def test_mcp_provider_discovers_and_calls_search_tool() -> None:
    client = MCPClient()
    register_web_search(client, DemoSearchProvider())
    provider = MCPWebSearchProvider(client)

    results = provider.search(ResearchQuery(question="What are operational risks?"), limit=1)

    assert len(client.discover_tools()) == 1
    assert len(results) == 1
    assert results[0].title.startswith("PolyAnalyst")


def test_mcp_client_enforces_timeout() -> None:
    client = MCPClient(timeout_seconds=0.01)
    client.register(
        ToolDefinition(name="slow", description="slow test tool"),
        lambda _: time.sleep(0.1),
    )
    with pytest.raises(MCPToolError, match="timed out"):
        client.call("slow", {})


def test_read_only_database_tool_rejects_writes(tmp_path) -> None:
    path = tmp_path / "data.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE values_table (value INTEGER)")
        connection.execute("INSERT INTO values_table VALUES (4)")
    tool = ReadOnlyDatabaseTool(path)

    assert tool.query("SELECT value FROM values_table") == [{"value": 4}]
    with pytest.raises(UnsafeQueryError):
        tool.query("DELETE FROM values_table")


def test_cache_and_budget_are_explicit(tmp_path) -> None:
    cache = JsonCache(tmp_path / "cache.db")
    try:
        key = cache.key("search", {"query": "risk"})
        cache.set(key, {"value": 1})
        assert cache.get(key) == {"value": 1}
    finally:
        cache.close()

    budget = BudgetTracker(max_cost_usd=0.1, max_duration_seconds=10, max_sources=1)
    budget.record(sources=1)
    with pytest.raises(BudgetExceeded, match="source budget"):
        budget.record(sources=1)


def test_data_path_policy_blocks_traversal(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    data_file = allowed / "data.csv"
    data_file.write_text("value\n1\n", encoding="utf-8")
    policy = DataPathPolicy([allowed])
    assert policy.validate(data_file) == data_file.resolve()
    with pytest.raises(PermissionError):
        policy.validate(tmp_path / "outside.csv")
