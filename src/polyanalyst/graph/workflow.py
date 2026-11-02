"""Stateful multi-agent research workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from polyanalyst.agents.analyst import DataAnalystAgent
from polyanalyst.agents.base import AgentOutput
from polyanalyst.agents.critic import RiskCriticAgent
from polyanalyst.agents.rag import RAGAgent
from polyanalyst.agents.research import ResearchAgent
from polyanalyst.agents.supervisor import SupervisorAgent
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.graph.state import WorkflowResult, WorkflowState
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.llm.base import LLMProvider
from polyanalyst.models import (
    ApprovalRequest,
    ResearchQuery,
    ResearchTask,
    RunEvent,
    RunStatus,
    TaskKind,
    TaskStatus,
)
from polyanalyst.reporting.drafting import DraftReport, ReportGenerator
from polyanalyst.reporting.reviewer import ReviewerAgent
from polyanalyst.tools.budgets import BudgetExceeded


class ResearchWorkflow:
    """Execute the supervisor-created DAG and persist every major transition."""

    def __init__(
        self,
        evidence_store: SQLiteEvidenceStore,
        run_repository: RunRepository,
        *,
        document_store: InMemoryDocumentStore | None = None,
        supervisor: SupervisorAgent | None = None,
        research_agent: ResearchAgent | None = None,
        rag_agent: RAGAgent | None = None,
        data_analyst: DataAnalystAgent | None = None,
        critic: RiskCriticAgent | None = None,
        reporter: ReportGenerator | None = None,
        reviewer: ReviewerAgent | None = None,
        llm: LLMProvider | None = None,
        max_workers: int = 3,
    ) -> None:
        self.evidence_store = evidence_store
        self.run_repository = run_repository
        self.document_store = document_store or InMemoryDocumentStore()
        self.supervisor = supervisor or SupervisorAgent()
        self.research_agent = research_agent or ResearchAgent()
        self.rag_agent = rag_agent or RAGAgent(self.document_store)
        self.data_analyst = data_analyst or DataAnalystAgent()
        self.critic = critic or RiskCriticAgent()
        self.reporter = reporter or ReportGenerator(llm=llm)
        self.reviewer = reviewer or ReviewerAgent()
        self.max_workers = max(1, max_workers)

    def run(
        self,
        query: ResearchQuery,
        *,
        approve_plan: bool = False,
        human_approval: bool | None = None,
    ) -> WorkflowResult:
        """Create a run and either return its plan or execute the approved DAG."""

        run = self.run_repository.create_run(query)
        clarification_questions = self.supervisor.assess_clarification(query)
        plan = self.supervisor.create_plan(query)
        self.supervisor.validate_plan(plan)
        run.plan_id = plan.plan_id
        run.status = RunStatus.WAITING_FOR_PLAN_APPROVAL
        self.run_repository.save_run(run)
        state = WorkflowState(
            run_id=run.run_id,
            query=query,
            status=RunStatus.WAITING_FOR_PLAN_APPROVAL,
            plan=plan,
            clarification_questions=clarification_questions,
        )
        self._emit(
            run.run_id,
            "plan_created",
            "Research plan created",
            payload={"plan_id": plan.plan_id},
        )
        self._checkpoint(state)
        if not approve_plan:
            return WorkflowResult(state=state)
        state.plan = self.supervisor.approve(plan)
        return self._execute(state, human_approval=human_approval)

    def resume(
        self,
        run_id: str,
        *,
        approve_plan: bool = False,
        human_approval: bool | None = None,
    ) -> WorkflowResult:
        """Resume a plan-approval or human-approval pause from SQLite."""

        payload = self.run_repository.load_checkpoint(run_id)
        if payload is None:
            raise KeyError(f"No checkpoint found for run: {run_id}")
        state = WorkflowState.model_validate(payload)
        if state.status == RunStatus.WAITING_FOR_PLAN_APPROVAL:
            if not approve_plan or state.plan is None:
                return WorkflowResult(state=state)
            state.plan = self.supervisor.approve(state.plan)
        elif state.status == RunStatus.WAITING_FOR_HUMAN_APPROVAL:
            if human_approval is None:
                return WorkflowResult(state=state)
            if not human_approval:
                return self._fail(state, "Human approval was denied")
        return self._execute(state, human_approval=human_approval)

    def _execute(self, state: WorkflowState, human_approval: bool | None) -> WorkflowResult:
        if state.plan is None or not state.plan.approved:
            return WorkflowResult(state=state)
        started_at = datetime.now(UTC)
        if state.plan.estimated_cost_usd > state.query.max_cost_usd:
            return self._fail(state, "Estimated plan cost exceeds the configured cost budget")
        self.run_repository.update_status(
            state.run_id,
            RunStatus.RUNNING,
            started_at=started_at,
            plan_id=state.plan.plan_id,
        )
        state.status = RunStatus.RUNNING
        self._emit(state.run_id, "run_started", "Approved research run started")
        try:
            self._execute_tasks(state, started_at)
        except Exception as exc:
            return self._fail(state, str(exc))

        if state.plan.requires_approval and human_approval is None:
            state.approval_request = ApprovalRequest(
                run_id=state.run_id,
                reason="The plan or its findings meet the configured high-risk threshold.",
                risk_level=state.query.risk_level,
            )
            state.status = RunStatus.WAITING_FOR_HUMAN_APPROVAL
            self.run_repository.update_status(state.run_id, state.status)
            self._emit(
                state.run_id,
                "approval_requested",
                state.approval_request.reason,
                payload={"approval_id": state.approval_request.approval_id},
            )
            self._checkpoint(state)
            return WorkflowResult(state=state)
        if state.plan.requires_approval and human_approval is False:
            return self._fail(state, "Human approval was denied")
        return self._complete(state, started_at)

    def _execute_tasks(self, state: WorkflowState, started_at: datetime) -> None:
        assert state.plan is not None
        tasks_by_id = {task.task_id: task for task in state.plan.tasks}
        completed = set(state.completed_task_ids)
        while len(completed) < len(tasks_by_id):
            ready = [
                task
                for task in tasks_by_id.values()
                if task.task_id not in completed and set(task.dependencies).issubset(completed)
            ]
            if not ready:
                raise ValueError("No runnable tasks remain; the research plan is inconsistent")

            for task in ready:
                task.status = TaskStatus.RUNNING
                self._emit(
                    state.run_id,
                    "task_started",
                    task.title,
                    task.task_id,
                    {"kind": task.kind.value},
                )

            outputs: dict[str, AgentOutput] = {}
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(ready))) as executor:
                futures = {
                    executor.submit(self._execute_task_with_retry, state, task): task
                    for task in ready
                }
                for future in as_completed(futures):
                    task = futures[future]
                    outputs[task.task_id] = future.result()

            for task in ready:
                output = outputs[task.task_id]
                task.status = TaskStatus.COMPLETED
                task.output_refs = output.evidence_ids
                completed.add(task.task_id)
                state.completed_task_ids.append(task.task_id)
                if output.finding:
                    state.findings.append(output.finding)
                state.evidence_ids.extend(
                    evidence_id
                    for evidence_id in output.evidence_ids
                    if evidence_id not in state.evidence_ids
                )
                state.contradictions.extend(output.contradictions)
                self._emit(
                    state.run_id,
                    "task_completed",
                    output.summary,
                    task.task_id,
                    {"evidence_count": len(output.evidence_ids)},
                )
                self._checkpoint(state)
                self._check_budget(state, started_at)

    def _execute_task(self, state: WorkflowState, task: ResearchTask) -> AgentOutput:
        if task.kind == TaskKind.RESEARCH:
            return self.research_agent.run(
                state.query, state.run_id, task.task_id, self.evidence_store
            )
        if task.kind == TaskKind.RETRIEVAL:
            return self.rag_agent.run(state.query, state.run_id, task.task_id, self.evidence_store)
        if task.kind == TaskKind.DATA_ANALYSIS:
            return self.data_analyst.run(
                state.query, state.run_id, task.task_id, self.evidence_store
            )
        if task.kind == TaskKind.RISK_CRITIC:
            output = self.critic.run(state.query, state.run_id, self.evidence_store)
            return output
        if task.kind == TaskKind.REPORT:
            evidence = self.evidence_store.list_unique_evidence(state.run_id)
            draft = self.reporter.draft(
                state.query,
                evidence,
                state.findings,
                state.contradictions,
                self.evidence_store,
                state.run_id,
            )
            state.report_title = draft.title
            state.report_markdown = draft.markdown
            state.report_claims = draft.claims
            return AgentOutput(
                agent_name="reporter",
                summary=f"Reporter drafted {len(draft.claims)} evidence-linked claim(s).",
                evidence_ids=[evidence.evidence_id for evidence in evidence],
            )
        if task.kind == TaskKind.REVIEW:
            evidence = self.evidence_store.list_unique_evidence(state.run_id)
            draft = DraftReport(
                title=state.report_title or "Research report",
                markdown=state.report_markdown or "",
                claims=state.report_claims,
            )
            state.review = self.reviewer.review(draft, evidence, state.contradictions)
            if not state.review.passed:
                revised = self.reporter.revise(draft, state.review.revision_instructions)
                state.report_markdown = revised.markdown
            return AgentOutput(
                agent_name="reviewer",
                summary=(
                    f"Reviewer {'passed' if state.review.passed else 'requested revisions'} "
                    f"with {state.review.citation_coverage:.0%} citation coverage."
                ),
                evidence_ids=[evidence.evidence_id for evidence in evidence],
            )
        raise ValueError(f"Unsupported task kind: {task.kind}")

    def _execute_task_with_retry(self, state: WorkflowState, task: ResearchTask) -> AgentOutput:
        """Retry transient agent failures without exceeding the query budget."""

        while True:
            try:
                return self._execute_task(state, task)
            except Exception:
                task.retry_count += 1
                if task.retry_count > state.query.max_retries:
                    raise
                self._emit(
                    state.run_id,
                    "task_retry",
                    f"Retrying {task.title} ({task.retry_count}/{state.query.max_retries})",
                    task.task_id,
                    {"retry_count": task.retry_count},
                )

    def _check_budget(self, state: WorkflowState, started_at: datetime) -> None:
        """Stop a run as soon as a configured budget is crossed."""

        if state.plan and state.plan.estimated_cost_usd > state.query.max_cost_usd:
            raise BudgetExceeded("Configured cost budget was exceeded")
        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        if elapsed > state.query.max_duration_seconds:
            raise BudgetExceeded("Configured duration budget was exceeded")
        if len(self.evidence_store.list_evidence(state.run_id)) > state.query.max_sources:
            raise BudgetExceeded("Configured source budget was exceeded")

    def _complete(self, state: WorkflowState, started_at: datetime) -> WorkflowResult:
        state.status = RunStatus.COMPLETED
        finished_at = datetime.now(UTC)
        duration = (finished_at - started_at).total_seconds()
        self.run_repository.update_status(
            state.run_id,
            RunStatus.COMPLETED,
            report_markdown=state.report_markdown,
            finished_at=finished_at,
            total_cost_usd=state.plan.estimated_cost_usd if state.plan else 0.0,
            total_duration_seconds=duration,
        )
        self._emit(state.run_id, "run_completed", "Research report completed")
        self._checkpoint(state)
        return WorkflowResult(state=state)

    def _fail(self, state: WorkflowState, message: str) -> WorkflowResult:
        state.status = RunStatus.FAILED
        self.run_repository.update_status(state.run_id, RunStatus.FAILED, error=message)
        self._emit(state.run_id, "run_failed", message)
        self._checkpoint(state)
        return WorkflowResult(state=state)

    def _emit(
        self,
        run_id: str,
        event_type: str,
        message: str,
        task_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.run_repository.append_event(
            RunEvent(
                run_id=run_id,
                event_type=event_type,
                message=message,
                task_id=task_id,
                payload=payload or {},
            )
        )

    def _checkpoint(self, state: WorkflowState) -> None:
        self.run_repository.save_checkpoint(state.run_id, state.model_dump(mode="json"))
