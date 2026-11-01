"""Durable run history, events, and resumable workflow state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from polyanalyst.models import ResearchQuery, RunEvent, RunRecord, RunStatus, UserFeedback


class RunRepository:
    """Store run metadata and checkpoints in the same SQLite database."""

    def __init__(self, path: str | Path = "data/polyanalyst.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id);
                CREATE TABLE IF NOT EXISTS run_checkpoints (
                    run_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_run ON feedback(run_id);
                """
            )

    def create_run(self, query: ResearchQuery) -> RunRecord:
        run = RunRecord(query=query)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO runs(run_id, payload, created_at) VALUES (?, ?, ?)",
                (run.run_id, run.model_dump_json(), run.created_at.isoformat()),
            )
        return run

    def save_run(self, run: RunRecord) -> RunRecord:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO runs(run_id, payload, created_at) VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload
                """,
                (run.run_id, run.model_dump_json(), run.created_at.isoformat()),
            )
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._connection.execute(
            "SELECT payload FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return RunRecord.model_validate(json.loads(row["payload"])) if row else None

    def list_runs(self, limit: int = 50) -> list[RunRecord]:
        rows = self._connection.execute(
            "SELECT payload FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [RunRecord.model_validate(json.loads(row["payload"])) for row in rows]

    def append_event(self, event: RunEvent) -> RunEvent:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO run_events(event_id, run_id, payload, created_at) VALUES (?, ?, ?, ?)",
                (
                    event.event_id,
                    event.run_id,
                    event.model_dump_json(),
                    event.created_at.isoformat(),
                ),
            )
        return event

    def list_events(self, run_id: str) -> list[RunEvent]:
        rows = self._connection.execute(
            "SELECT payload FROM run_events WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()
        return [RunEvent.model_validate(json.loads(row["payload"])) for row in rows]

    def save_checkpoint(self, run_id: str, state: dict[str, object]) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO run_checkpoints(run_id, payload, created_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(run_id) DO UPDATE SET
                    payload=excluded.payload,
                    created_at=excluded.created_at
                """,
                (run_id, json.dumps(state, default=str)),
            )

    def load_checkpoint(self, run_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT payload FROM run_checkpoints WHERE run_id = ?", (run_id,)
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_feedback(self, feedback: UserFeedback) -> UserFeedback:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO feedback(feedback_id, run_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    feedback.feedback_id,
                    feedback.run_id,
                    feedback.model_dump_json(),
                    feedback.created_at.isoformat(),
                ),
            )
        return feedback

    def list_feedback(self, run_id: str | None = None) -> list[UserFeedback]:
        if run_id:
            rows = self._connection.execute(
                "SELECT payload FROM feedback WHERE run_id = ? ORDER BY created_at", (run_id,)
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT payload FROM feedback ORDER BY created_at"
            ).fetchall()
        return [UserFeedback.model_validate(json.loads(row["payload"])) for row in rows]

    def compare_runs(self, first_run_id: str, second_run_id: str) -> dict[str, object]:
        """Return stable, presentation-ready differences between two runs."""

        first = self.get_run(first_run_id)
        second = self.get_run(second_run_id)
        if first is None or second is None:
            raise KeyError("Both run IDs must exist before comparison")
        return {
            "first_run_id": first.run_id,
            "second_run_id": second.run_id,
            "status": {"first": first.status.value, "second": second.status.value},
            "cost_delta_usd": round(second.total_cost_usd - first.total_cost_usd, 6),
            "duration_delta_seconds": round(
                second.total_duration_seconds - first.total_duration_seconds, 6
            ),
            "query_changed": first.query != second.query,
            "report_changed": first.report_markdown != second.report_markdown,
        }

    def update_status(self, run_id: str, status: RunStatus, **updates: object) -> RunRecord:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")
        run.status = status
        for key, value in updates.items():
            setattr(run, key, value)
        return self.save_run(run)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> RunRepository:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
