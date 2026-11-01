"""Small SQLite-backed cache for repeatable tool calls."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class JsonCache:
    """Cache JSON-compatible values with a time-to-live."""

    def __init__(self, path: str | Path = "data/cache.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )

    @staticmethod
    def key(namespace: str, value: object) -> str:
        serialized = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
        digest = hashlib.sha256(serialized).hexdigest()
        return f"{namespace}:{digest}"

    def get(self, cache_key: str) -> Any | None:
        row = self._connection.execute(
            "SELECT payload, expires_at FROM cache WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row is None:
            return None
        if row[1] <= time.time():
            self.delete(cache_key)
            return None
        return json.loads(row[0])

    def set(self, cache_key: str, value: Any, ttl_seconds: int = 900) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO cache(cache_key, payload, expires_at) VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload=excluded.payload, expires_at=excluded.expires_at
                """,
                (cache_key, json.dumps(value, default=str), time.time() + ttl_seconds),
            )

    def delete(self, cache_key: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM cache WHERE cache_key = ?", (cache_key,))

    def close(self) -> None:
        self._connection.close()
