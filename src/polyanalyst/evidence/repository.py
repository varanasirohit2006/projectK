"""SQLite-backed evidence store with explicit provenance relationships."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from polyanalyst.models import EvidenceItem, ReportClaim, Source


class SQLiteEvidenceStore:
    """Persist sources, evidence, and claim-to-evidence relationships."""

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
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    content_hash TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sources_run ON sources(run_id);
                CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash);

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    source_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_id) REFERENCES sources(source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence(run_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_id);

                CREATE TABLE IF NOT EXISTS report_claims (
                    claim_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claim_evidence (
                    claim_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    PRIMARY KEY (claim_id, evidence_id),
                    FOREIGN KEY(claim_id) REFERENCES report_claims(claim_id),
                    FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id)
                );
                """
            )

    def add_source(self, source: Source, run_id: str | None = None) -> Source:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO sources(source_id, run_id, content_hash, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    content_hash=excluded.content_hash,
                    payload=excluded.payload
                """,
                (
                    source.source_id,
                    run_id,
                    source.content_hash,
                    source.model_dump_json(),
                    source.retrieved_at.isoformat(),
                ),
            )
        return source

    def add_evidence(self, evidence: EvidenceItem) -> EvidenceItem:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO evidence(evidence_id, run_id, source_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    source_id=excluded.source_id,
                    payload=excluded.payload
                """,
                (
                    evidence.evidence_id,
                    evidence.run_id,
                    evidence.source_id,
                    evidence.model_dump_json(),
                    evidence.created_at.isoformat(),
                ),
            )
        return evidence

    def add_claim(self, claim: ReportClaim, run_id: str | None = None) -> ReportClaim:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO report_claims(claim_id, run_id, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(claim_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    payload=excluded.payload
                """,
                (claim.claim_id, run_id, claim.model_dump_json(), datetime.now(UTC).isoformat()),
            )
            self._connection.executemany(
                "INSERT OR IGNORE INTO claim_evidence(claim_id, evidence_id) VALUES (?, ?)",
                [(claim.claim_id, evidence_id) for evidence_id in claim.evidence_ids],
            )
        return claim

    def get_source(self, source_id: str) -> Source | None:
        row = self._connection.execute(
            "SELECT payload FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        return Source.model_validate(json.loads(row["payload"])) if row else None

    def get_evidence(self, evidence_id: str) -> EvidenceItem | None:
        row = self._connection.execute(
            "SELECT payload FROM evidence WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        return EvidenceItem.model_validate(json.loads(row["payload"])) if row else None

    def list_evidence(self, run_id: str | None = None) -> list[EvidenceItem]:
        if run_id:
            rows = self._connection.execute(
                "SELECT payload FROM evidence WHERE run_id = ? ORDER BY created_at", (run_id,)
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT payload FROM evidence ORDER BY created_at"
            ).fetchall()
        return [EvidenceItem.model_validate(json.loads(row["payload"])) for row in rows]

    def list_unique_evidence(self, run_id: str | None = None) -> list[EvidenceItem]:
        """Return one strongest item per normalized claim."""

        from polyanalyst.evidence.quality import deduplicate_evidence

        return deduplicate_evidence(self.list_evidence(run_id))

    def get_claim(self, claim_id: str) -> ReportClaim | None:
        row = self._connection.execute(
            "SELECT payload FROM report_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return ReportClaim.model_validate(json.loads(row["payload"])) if row else None

    def evidence_for_claim(self, claim_id: str) -> list[EvidenceItem]:
        rows = self._connection.execute(
            """
            SELECT e.payload
            FROM evidence e
            JOIN claim_evidence ce ON ce.evidence_id = e.evidence_id
            WHERE ce.claim_id = ?
            ORDER BY e.created_at
            """,
            (claim_id,),
        ).fetchall()
        return [EvidenceItem.model_validate(json.loads(row["payload"])) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> SQLiteEvidenceStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
