"""A small MCP-shaped tool client.

The registry is useful for local development and tests. A network MCP
transport can implement the same ``discover_tools`` and ``call`` methods
without coupling agents to a particular SDK.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolError(RuntimeError):
    """Raised when a tool is unknown, invalid, or times out."""


ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass
class _RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class MCPClient:
    """Discover and invoke explicitly registered tools."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._tools: dict[str, _RegisteredTool] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        if definition.name in self._tools:
            raise MCPToolError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = _RegisteredTool(definition, handler)

    def discover_tools(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        registered = self._tools.get(name)
        if registered is None:
            raise MCPToolError(f"Unknown MCP tool: {name}")
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(registered.handler, arguments)
        try:
            return future.result(timeout=self.timeout_seconds)
        except TimeoutError as exc:
            future.cancel()
            raise MCPToolError(f"Tool timed out: {name}") from exc
        except Exception as exc:
            raise MCPToolError(f"Tool failed: {name}: {exc}") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
