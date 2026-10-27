"""Shared domain models used by agents, persistence, and the UI."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def new_id(prefix: str) -> str:
    """Create a readable, globally unique identifier."""

    return f"{prefix}_{uuid4().hex[:12]}"


class TaskKind(StrEnum):
    RESEARCH = "research"
    RETRIEVAL = "retrieval"
    DATA_ANALYSIS = "data_analysis"
    RISK_CRITIC = "risk_critic"
    REPORT = "report"
    REVIEW = "review"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


class RunStatus(StrEnum):
    CREATED = "created"
    WAITING_FOR_PLAN_APPROVAL = "waiting_for_plan_approval"
    RUNNING = "running"
    WAITING_FOR_HUMAN_APPROVAL = "waiting_for_human_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceType(StrEnum):
    WEB = "web"
    DOCUMENT = "document"
    DATASET = "dataset"
    DATABASE = "database"


class PolyModel(BaseModel):
    """Base model with strict serialization settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ResearchQuery(PolyModel):
    question: str = Field(min_length=3)
    geography: str | None = None
    time_period: str | None = None
    audience: str | None = None
    output_format: str = "markdown"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    collection_ids: list[str] = Field(default_factory=list)
    data_paths: list[str] = Field(default_factory=list)
    max_sources: int = Field(default=10, ge=1, le=100)
    max_cost_usd: float = Field(default=1.0, ge=0)
    max_duration_seconds: int = Field(default=300, ge=1)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return " ".join(value.split())


class ResearchTask(PolyModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    kind: TaskKind
    title: str
    description: str
    agent_name: str
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = Field(default=0, ge=0)
    output_refs: list[str] = Field(default_factory=list)


class ResearchPlan(PolyModel):
    plan_id: str = Field(default_factory=lambda: new_id("plan"))
    query: ResearchQuery
    tasks: list[ResearchTask]
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    estimated_duration_seconds: int = Field(default=0, ge=0)
    requires_approval: bool = False
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Source(PolyModel):
    source_id: str = Field(default_factory=lambda: new_id("src"))
    url: str | None = None
    document_id: str | None = None
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_type: SourceType
    content_hash: str
    quality_score: float = Field(default=0.5, ge=0, le=1)
    freshness_score: float = Field(default=0.5, ge=0, le=1)

    @field_validator("url", "document_id")
    @classmethod
    def require_reference(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class EvidenceItem(PolyModel):
    evidence_id: str = Field(default_factory=lambda: new_id("evidence"))
    run_id: str | None = None
    claim: str = Field(min_length=3)
    excerpt: str = Field(min_length=1)
    source_id: str
    location: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    quality_score: float = Field(default=0.5, ge=0, le=1)
    freshness_score: float = Field(default=0.5, ge=0, le=1)
    task_id: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Finding(PolyModel):
    finding_id: str = Field(default_factory=lambda: new_id("finding"))
    run_id: str | None = None
    agent_name: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Contradiction(PolyModel):
    contradiction_id: str = Field(default_factory=lambda: new_id("contradiction"))
    claim_a: str
    claim_b: str
    evidence_ids: list[str] = Field(default_factory=list)
    resolution: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class ReportClaim(PolyModel):
    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    supported: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)


class ReviewResult(PolyModel):
    review_id: str = Field(default_factory=lambda: new_id("review"))
    passed: bool
    citation_coverage: float = Field(default=0.0, ge=0, le=1)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    contradiction_ids: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRequest(PolyModel):
    approval_id: str = Field(default_factory=lambda: new_id("approval"))
    run_id: str
    reason: str
    risk_level: RiskLevel
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decision: str | None = None
    decided_at: datetime | None = None


class RunEvent(PolyModel):
    event_id: str = Field(default_factory=lambda: new_id("event"))
    run_id: str
    event_type: str
    message: str
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunRecord(PolyModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    query: ResearchQuery
    status: RunStatus = RunStatus.CREATED
    plan_id: str | None = None
    report_markdown: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_cost_usd: float = Field(default=0.0, ge=0)
    total_duration_seconds: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
