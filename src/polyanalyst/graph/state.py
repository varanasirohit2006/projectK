"""Serializable state for a resumable research run."""

from __future__ import annotations

from pydantic import Field

from polyanalyst.models import (
    ApprovalRequest,
    Contradiction,
    Finding,
    PolyModel,
    ReportClaim,
    ReportImage,
    ResearchPlan,
    ResearchQuery,
    ReviewResult,
    RunStatus,
)


class WorkflowState(PolyModel):
    run_id: str
    query: ResearchQuery
    status: RunStatus
    plan: ResearchPlan | None = None
    clarification_questions: list[str] = Field(default_factory=list)
    completed_task_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    report_title: str | None = None
    report_markdown: str | None = None
    report_claims: list[ReportClaim] = Field(default_factory=list)
    report_images: list[ReportImage] = Field(default_factory=list)
    review: ReviewResult | None = None
    approval_request: ApprovalRequest | None = None


class WorkflowResult(PolyModel):
    state: WorkflowState

    @property
    def run_id(self) -> str:
        return self.state.run_id

    @property
    def status(self) -> RunStatus:
        return self.state.status
