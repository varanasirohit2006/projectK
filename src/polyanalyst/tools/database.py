"""Read-only SQL tool with a deliberately narrow execution policy."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any


class UnsafeQueryError(ValueError):
    """Raised when a query is not a read-only single statement."""


class ReadOnlyDatabaseTool:
    """Execute bounded SELECT/WITH queries against a SQLite database."""

    _forbidden = re.compile(
        r"\b(insert|update|delete|drop|alter|attach|detach|replace|vacuum|pragma|create)\b",
        re.IGNORECASE,
    )

    def __init__(self, path: str | Path, max_rows: int = 1_000) -> None:
        self.path = Path(path)
        self.max_rows = max_rows

    def query(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        normalized = sql.strip().rstrip(";").strip()
        if not normalized or self._forbidden.search(normalized):
            raise UnsafeQueryError("Only read-only SELECT queries are allowed")
        if not re.match(r"^(select|with)\b", normalized, re.IGNORECASE):
            raise UnsafeQueryError("Query must start with SELECT or WITH")
        if ";" in normalized:
            raise UnsafeQueryError("Multiple SQL statements are not allowed")
        with sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(normalized, parameters).fetchmany(self.max_rows)
        return [dict(row) for row in rows]
