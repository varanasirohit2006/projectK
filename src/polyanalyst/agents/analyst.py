"""Restricted descriptive data-analysis agent."""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path

from polyanalyst.agents.base import AgentOutput
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.models import EvidenceItem, Finding, ResearchQuery, Source, SourceType
from polyanalyst.security.guardrails import DataPathPolicy


class DataAnalystAgent:
    """Analyze CSV files without executing arbitrary user code."""

    def __init__(
        self,
        max_bytes: int = 5_000_000,
        path_policy: DataPathPolicy | None = None,
    ) -> None:
        self.max_bytes = max_bytes
        self.path_policy = path_policy

    def run(
        self,
        query: ResearchQuery,
        run_id: str,
        task_id: str,
        store: SQLiteEvidenceStore,
    ) -> AgentOutput:
        evidence_ids: list[str] = []
        summaries: list[str] = []
        for raw_path in query.data_paths:
            path = self.path_policy.validate(raw_path) if self.path_policy else Path(raw_path)
            if path.suffix.lower() != ".csv":
                raise ValueError(f"Unsupported data file: {path.name}; only CSV is allowed")
            if path.stat().st_size > self.max_bytes:
                raise ValueError(f"Data file is larger than the {self.max_bytes} byte limit")
            rows, numeric = self._read_csv(path)
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            source = Source(
                document_id=str(path.resolve()),
                title=path.name,
                source_type=SourceType.DATASET,
                content_hash=content_hash,
                quality_score=0.85,
                freshness_score=0.8,
            )
            store.add_source(source, run_id=run_id)
            for column, values in numeric.items():
                if not values:
                    continue
                mean = sum(values) / len(values)
                claim = (
                    f"Dataset {path.name} contains {len(rows)} row(s); column {column} "
                    f"has mean {mean:.2f}, minimum {min(values):.2f}, "
                    f"and maximum {max(values):.2f}."
                )
                evidence = EvidenceItem(
                    run_id=run_id,
                    claim=claim,
                    excerpt=claim,
                    source_id=source.source_id,
                    location=f"column {column}",
                    confidence=0.95,
                    quality_score=source.quality_score,
                    freshness_score=source.freshness_score,
                    task_id=task_id,
                    agent_id="data_analyst",
                    metadata={"row_count": len(rows), "column": column},
                )
                store.add_evidence(evidence)
                evidence_ids.append(evidence.evidence_id)
                summaries.append(claim)

        summary = (
            f"Data analyst generated {len(evidence_ids)} numeric finding(s)."
            if evidence_ids
            else "Data analyst found no numeric columns to summarize."
        )
        finding = Finding(
            run_id=run_id,
            agent_name="data_analyst",
            summary=summary,
            evidence_ids=evidence_ids,
            metrics={"finding_count": float(len(evidence_ids))},
        )
        return AgentOutput(
            agent_name="data_analyst",
            summary=summary,
            evidence_ids=evidence_ids,
            finding=finding,
            metadata={"summaries": summaries},
        )

    def _read_csv(self, path: Path) -> tuple[list[dict[str, str]], dict[str, list[float]]]:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        numeric: dict[str, list[float]] = {}
        for row in rows:
            for column, raw_value in row.items():
                if raw_value is None or not raw_value.strip():
                    continue
                try:
                    value = float(raw_value)
                except ValueError:
                    continue
                if math.isfinite(value):
                    numeric.setdefault(column, []).append(value)
        return rows, numeric
