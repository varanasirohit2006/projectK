"""Deterministic supervisor and DAG planner.

The planner is intentionally model-independent. A hosted LLM planner can be
introduced behind the same interface later without changing workflow state or
the specialist agents.
"""

from __future__ import annotations

from polyanalyst.models import ResearchPlan, ResearchQuery, ResearchTask, RiskLevel, TaskKind


class SupervisorAgent:
    """Create and validate a reviewable plan for a research question."""

    _HIGH_RISK_TERMS = {
        "invest",
        "investment",
        "medical",
        "clinical",
        "legal",
        "safety",
        "recommend",
        "recommendation",
        "financial",
    }

    def assess_clarification(self, query: ResearchQuery) -> list[str]:
        """Return missing scope fields that materially affect research."""

        questions: list[str] = []
        question = query.question.lower()
        if len(question.split()) < 5:
            questions.append("What outcome or decision should the analysis support?")
        if not query.time_period and any(
            term in question for term in ("trend", "outlook", "forecast", "current", "risk")
        ):
            questions.append("What time period should the analysis cover?")
        if not query.geography and any(
            term in question for term in ("market", "industry", "supply chain", "regulation")
        ):
            questions.append("What geography or market should be included?")
        return questions

    def create_plan(self, query: ResearchQuery) -> ResearchPlan:
        """Build a DAG whose task IDs are stable within the returned plan."""

        research = ResearchTask(
            kind=TaskKind.RESEARCH,
            title="Research current external sources",
            description="Find recent, relevant sources and extract citable claims.",
            agent_name="research",
        )
        retrieval = ResearchTask(
            kind=TaskKind.RETRIEVAL,
            title="Retrieve private knowledge",
            description="Search selected private document collections for supporting context.",
            agent_name="rag",
        )
        tasks = [research, retrieval]

        if query.data_paths:
            tasks.append(
                ResearchTask(
                    kind=TaskKind.DATA_ANALYSIS,
                    title="Analyze supplied data",
                    description="Run safe descriptive analysis over the selected data files.",
                    agent_name="data_analyst",
                )
            )

        evidence_task_ids = [task.task_id for task in tasks]
        critic = ResearchTask(
            kind=TaskKind.RISK_CRITIC,
            title="Synthesize risks and evidence gaps",
            description="Compare findings, identify risks, and surface contradictions.",
            agent_name="critic",
            dependencies=evidence_task_ids,
        )
        report = ResearchTask(
            kind=TaskKind.REPORT,
            title="Draft a cited report",
            description="Assemble an evidence-backed report with traceable claims.",
            agent_name="reporter",
            dependencies=[critic.task_id],
        )
        review = ResearchTask(
            kind=TaskKind.REVIEW,
            title="Review claims and citations",
            description="Check citation coverage and flag unsupported statements.",
            agent_name="reviewer",
            dependencies=[report.task_id],
        )
        tasks.extend([critic, report, review])

        question_terms = set(query.question.lower().replace("-", " ").split())
        requires_approval = query.risk_level == RiskLevel.HIGH or bool(
            question_terms.intersection(self._HIGH_RISK_TERMS)
        )
        return ResearchPlan(
            query=query,
            tasks=tasks,
            estimated_cost_usd=round(0.02 * len(tasks), 4),
            estimated_duration_seconds=15 * len(tasks),
            requires_approval=requires_approval,
        )

    def validate_plan(self, plan: ResearchPlan) -> None:
        """Raise ``ValueError`` when dependencies do not form a valid DAG."""

        task_ids = {task.task_id for task in plan.tasks}
        if len(task_ids) != len(plan.tasks):
            raise ValueError("Research plan contains duplicate task IDs")
        for task in plan.tasks:
            missing = set(task.dependencies) - task_ids
            if missing:
                raise ValueError(f"Task {task.task_id} has unknown dependencies: {sorted(missing)}")

        resolved: set[str] = set()
        remaining = {task.task_id: set(task.dependencies) for task in plan.tasks}
        while remaining:
            ready = {task_id for task_id, deps in remaining.items() if not deps - resolved}
            if not ready:
                raise ValueError("Research plan contains a dependency cycle")
            resolved.update(ready)
            for task_id in ready:
                remaining.pop(task_id)

    def approve(self, plan: ResearchPlan) -> ResearchPlan:
        """Return an approved copy after validating the plan."""

        self.validate_plan(plan)
        return plan.model_copy(update={"approved": True})
