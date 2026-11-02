"""Streamlit research workbench for PolyAnalyst."""

from __future__ import annotations

from pathlib import Path

from polyanalyst.agents.analyst import DataAnalystAgent
from polyanalyst.config import Settings
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.graph.state import WorkflowResult, WorkflowState
from polyanalyst.graph.workflow import ResearchWorkflow
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.llm.factory import build_llm_provider
from polyanalyst.models import ResearchQuery, RiskLevel, RunStatus, UserFeedback
from polyanalyst.reporting.drafting import DraftReport
from polyanalyst.reporting.export import export_pdf
from polyanalyst.security.guardrails import DataPathPolicy


def _workflow() -> ResearchWorkflow:
    import streamlit as st

    if "workflow" not in st.session_state:
        settings = Settings.from_env()
        settings.data_dir.joinpath("uploads").mkdir(parents=True, exist_ok=True)
        evidence = SQLiteEvidenceStore(settings.db_path)
        runs = RunRepository(settings.db_path)
        documents = InMemoryDocumentStore()
        uploads = settings.data_dir / "uploads"
        analyst = DataAnalystAgent(
            path_policy=DataPathPolicy([uploads]),
        )
        st.session_state.workflow_resources = (evidence, runs)
        st.session_state.settings = settings
        st.session_state.workflow = ResearchWorkflow(
            evidence,
            runs,
            document_store=documents,
            data_analyst=analyst,
            llm=build_llm_provider(settings),
        )
    return st.session_state.workflow


def _load_saved_run(workflow: ResearchWorkflow, run_id: str) -> WorkflowResult | None:
    import streamlit as st

    payload = workflow.run_repository.load_checkpoint(run_id)
    if payload is None:
        st.error("The selected run has no recoverable checkpoint.")
        return None
    return WorkflowResult(state=WorkflowState.model_validate(payload))


def _show_history(workflow: ResearchWorkflow) -> None:
    import streamlit as st

    st.subheader("Recent runs")
    for run in workflow.run_repository.list_runs(limit=8):
        label = f"{run.status.value} · {run.query.question[:42]}"
        if st.button(label, key=f"load-{run.run_id}", use_container_width=True):
            result = _load_saved_run(workflow, run.run_id)
            if result:
                st.session_state.result = result
                st.rerun()


def _save_uploads(workflow: ResearchWorkflow, text_file, csv_file) -> list[str]:
    import streamlit as st

    settings: Settings = st.session_state.settings
    data_paths: list[str] = []
    if text_file is not None:
        workflow.document_store.add_text(
            text_file.name,
            text_file.name,
            text_file.getvalue().decode("utf-8", errors="replace"),
            collection_id="uploads",
        )
    if csv_file is not None:
        destination = settings.data_dir / "uploads" / Path(csv_file.name).name
        destination.write_bytes(csv_file.getvalue())
        data_paths.append(str(destination))
    return data_paths


def _display_approval(workflow: ResearchWorkflow, result: WorkflowResult) -> None:
    import streamlit as st

    state = result.state
    if state.status == RunStatus.WAITING_FOR_PLAN_APPROVAL:
        st.warning("Review the plan before execution begins.")
        if st.button("Approve research plan", type="primary", key="approve-plan"):
            st.session_state.result = workflow.resume(state.run_id, approve_plan=True)
            st.rerun()
    elif state.status == RunStatus.WAITING_FOR_HUMAN_APPROVAL:
        reason = state.approval_request.reason if state.approval_request else "Approval required"
        st.error(reason)
        left, right = st.columns(2)
        if left.button("Approve and execute", type="primary", key="approve-risk"):
            st.session_state.result = workflow.resume(state.run_id, human_approval=True)
            st.rerun()
        if right.button("Reject", key="reject-risk"):
            st.session_state.result = workflow.resume(state.run_id, human_approval=False)
            st.rerun()


def _display_plan(state: WorkflowState) -> None:
    import streamlit as st

    if state.plan is None:
        return
    st.image("docs/assets/workflow-dag.svg", caption="The execution DAG", use_container_width=True)
    task_titles = {task.task_id: task.title for task in state.plan.tasks}
    st.dataframe(
        [
            {
                "task": task.title,
                "agent": task.agent_name,
                "status": task.status.value,
                "depends_on": ", ".join(task_titles.get(item, item) for item in task.dependencies)
                or "none",
                "outputs": len(task.output_refs),
            }
            for task in state.plan.tasks
        ],
        use_container_width=True,
        hide_index=True,
    )


def _display_evidence(workflow: ResearchWorkflow, state: WorkflowState) -> None:
    import streamlit as st

    evidence = workflow.evidence_store.list_unique_evidence(state.run_id)
    st.caption(f"{len(evidence)} unique evidence item(s) for this run")
    for index, item in enumerate(evidence, start=1):
        source = workflow.evidence_store.get_source(item.source_id)
        source_name = source.title if source else item.source_id
        with st.expander(f"E{index} · {source_name} · confidence {item.confidence:.0%}"):
            st.markdown(item.excerpt)
            st.write(
                {
                    "source": source.url if source and source.url else source_name,
                    "location": item.location or "not specified",
                    "quality": f"{item.quality_score:.0%}",
                    "freshness": f"{item.freshness_score:.0%}",
                    "agent": item.agent_id,
                    "prompt_injection_flagged": item.metadata.get(
                        "prompt_injection_flagged", False
                    ),
                }
            )


def _display_audit(workflow: ResearchWorkflow, state: WorkflowState) -> None:
    import streamlit as st

    events = workflow.run_repository.list_events(state.run_id)
    st.dataframe(
        [
            {
                "time": event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "event": event.event_type,
                "task": event.task_id or "run",
                "message": event.message,
            }
            for event in events
        ],
        use_container_width=True,
        hide_index=True,
    )
    if state.contradictions:
        st.subheader("Contradictions")
        for item in state.contradictions:
            st.error(f"{item.claim_a}  ↔  {item.claim_b}")
            st.caption(item.resolution or "No resolution recorded")
    if state.review:
        st.subheader("Review")
        st.write(
            {
                "passed": state.review.passed,
                "citation_coverage": f"{state.review.citation_coverage:.0%}",
                "unsupported_claims": state.review.unsupported_claim_ids,
            }
        )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="PolyAnalyst Research Workbench", layout="wide")
    st.title("PolyAnalyst Research Workbench")
    st.caption("Plan → evidence → critique → reviewed report")
    workflow = _workflow()
    settings: Settings = st.session_state.settings

    with st.sidebar:
        st.header("New research")
        question = st.text_area(
            "Research question",
            value="Analyze supply chain resilience and operational risks",
            height=110,
        )
        geography = st.text_input("Geography", placeholder="Global, India, Europe...")
        time_period = st.text_input("Time period", placeholder="Next 6 months, 2024–2026...")
        audience = st.text_input("Audience", placeholder="Executive team, analyst...")
        risk = st.selectbox("Risk level", [level.value for level in RiskLevel], index=1)
        max_sources = st.slider("Maximum evidence items", 1, 50, settings.max_sources)
        max_cost = st.number_input(
            "Maximum estimated cost (USD)", 0.0, 100.0, settings.max_cost_usd
        )
        max_duration = st.number_input(
            "Maximum duration (seconds)", 1, 3600, settings.max_duration_seconds
        )
        st.divider()
        text_file = st.file_uploader("Private document", type=["txt", "md"])
        csv_file = st.file_uploader("CSV dataset", type=["csv"])
        if st.button("Create research plan", type="primary", use_container_width=True):
            data_paths = _save_uploads(workflow, text_file, csv_file)
            query = ResearchQuery(
                question=question,
                geography=geography or None,
                time_period=time_period or None,
                audience=audience or None,
                risk_level=risk,
                collection_ids=["uploads"] if text_file else [],
                data_paths=data_paths,
                max_sources=max_sources,
                max_cost_usd=max_cost,
                max_duration_seconds=max_duration,
            )
            st.session_state.result = workflow.run(query)
            st.rerun()
        st.divider()
        _show_history(workflow)

    result = st.session_state.get("result")
    if result is None:
        st.info("Define a question in the sidebar to create a reviewable research plan.")
        st.image("docs/assets/architecture-overview.svg", use_container_width=True)
        return

    state = result.state
    record = workflow.run_repository.get_run(state.run_id)
    st.markdown(f"**Run:** `{state.run_id}`  ·  **Question:** {state.query.question}")
    _display_approval(workflow, result)

    completed = len(state.completed_task_ids)
    task_count = len(state.plan.tasks) if state.plan else 0
    citation = f"{state.review.citation_coverage:.0%}" if state.review else "—"
    metrics = st.columns(5)
    metrics[0].metric("Status", state.status.value)
    metrics[1].metric("Tasks", f"{completed}/{task_count}")
    metrics[2].metric("Evidence", len(state.evidence_ids))
    metrics[3].metric("Citation coverage", citation)
    metrics[4].metric("Duration", f"{record.total_duration_seconds:.2f}s" if record else "—")

    if state.clarification_questions:
        st.info("Scope questions: " + " ".join(state.clarification_questions))

    overview, plan, evidence, report, audit = st.tabs(
        ["Overview", "Plan", "Evidence", "Report", "Audit"]
    )
    with overview:
        st.image(
            "docs/assets/report-structure.svg",
            caption="Report organization",
            use_container_width=True,
        )
        if state.report_markdown:
            st.markdown(state.report_markdown)
        else:
            st.info("The report will appear here after the approved run completes.")
    with plan:
        _display_plan(state)
    with evidence:
        _display_evidence(workflow, state)
    with report:
        if state.report_markdown:
            st.download_button(
                "Download Markdown",
                state.report_markdown,
                file_name=f"polyanalyst-{state.run_id}.md",
                mime="text/markdown",
            )
            st.markdown(state.report_markdown)
            if st.button("Prepare PDF", key="prepare-pdf"):
                pdf_path = settings.data_dir / f"{state.run_id}.pdf"
                export_pdf(
                    DraftReport(
                        title=state.report_title or "PolyAnalyst report",
                        markdown=state.report_markdown,
                        claims=state.report_claims,
                    ),
                    pdf_path,
                )
                st.session_state.pdf_path = pdf_path
            if st.session_state.get("pdf_path"):
                pdf_path = st.session_state.pdf_path
                st.download_button("Download PDF", pdf_path.read_bytes(), file_name=pdf_path.name)
        else:
            st.info("No report is available yet.")
    with audit:
        _display_audit(workflow, state)

    if state.status == RunStatus.COMPLETED:
        st.divider()
        st.subheader("Feedback")
        feedback_col, comment_col, submit_col = st.columns([1, 3, 1])
        rating = feedback_col.selectbox("Rating", ["useful", "incomplete", "incorrect"])
        comment = comment_col.text_input("Comment", placeholder="What should improve?")
        if submit_col.button("Save feedback"):
            workflow.run_repository.save_feedback(
                UserFeedback(run_id=state.run_id, rating=rating, comment=comment or None)
            )
            st.success("Feedback saved for evaluation.")


if __name__ == "__main__":  # pragma: no cover
    main()
