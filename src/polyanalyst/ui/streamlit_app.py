"""Streamlit interface for plan approval, execution, and evidence inspection."""

from __future__ import annotations

from pathlib import Path

from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.graph.workflow import ResearchWorkflow
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.models import ResearchQuery, RiskLevel, RunStatus


def _workflow() -> ResearchWorkflow:
    import streamlit as st

    if "workflow" not in st.session_state:
        database = Path("data/polyanalyst.db")
        evidence = SQLiteEvidenceStore(database)
        runs = RunRepository(database)
        documents = InMemoryDocumentStore()
        st.session_state.workflow_resources = (evidence, runs)
        st.session_state.workflow = ResearchWorkflow(evidence, runs, document_store=documents)
    return st.session_state.workflow


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="PolyAnalyst", layout="wide")
    st.title("PolyAnalyst")
    st.caption("Evidence-backed multi-agent research with explicit approval gates")
    workflow = _workflow()

    with st.sidebar:
        st.header("Research scope")
        question = st.text_area(
            "Research question",
            value="Analyze supply chain resilience and operational risks",
            height=120,
        )
        geography = st.text_input("Geography", value="")
        time_period = st.text_input("Time period", value="")
        risk = st.selectbox("Risk level", [level.value for level in RiskLevel], index=1)
        uploaded = st.file_uploader("Private text or CSV", type=["txt", "md", "csv"])
        if uploaded is not None:
            documents = workflow.document_store
            documents.add_text(
                uploaded.name,
                uploaded.name,
                uploaded.getvalue().decode("utf-8", errors="replace"),
                collection_id="uploads",
            )
        if st.button("Create research plan", type="primary"):
            query = ResearchQuery(
                question=question,
                geography=geography or None,
                time_period=time_period or None,
                risk_level=risk,
                collection_ids=["uploads"] if uploaded else [],
            )
            st.session_state.result = workflow.run(query)

    result = st.session_state.get("result")
    if result is None:
        st.info("Enter a question and create a plan to begin.")
        return

    state = result.state
    if state.plan:
        st.subheader("Plan preview")
        st.dataframe(
            [
                {
                    "task": task.title,
                    "agent": task.agent_name,
                    "depends_on": ", ".join(task.dependencies) or "none",
                }
                for task in state.plan.tasks
            ],
            use_container_width=True,
        )
        if state.clarification_questions:
            st.warning("Scope questions: " + " ".join(state.clarification_questions))

    if state.status == RunStatus.WAITING_FOR_PLAN_APPROVAL and st.button("Approve plan"):
        st.session_state.result = workflow.resume(state.run_id, approve_plan=True)
        st.rerun()
    elif state.status == RunStatus.WAITING_FOR_HUMAN_APPROVAL:
        st.warning(state.approval_request.reason if state.approval_request else "Approval required")
        if st.button("Approve high-risk result"):
            st.session_state.result = workflow.resume(state.run_id, human_approval=True)
            st.rerun()
        if st.button("Reject result"):
            st.session_state.result = workflow.resume(state.run_id, human_approval=False)
            st.rerun()

    st.metric("Status", state.status.value)
    st.metric("Evidence items", len(state.evidence_ids))
    if state.review:
        st.metric("Citation coverage", f"{state.review.citation_coverage:.0%}")
    if state.report_markdown:
        st.subheader("Report")
        st.markdown(state.report_markdown)


if __name__ == "__main__":  # pragma: no cover
    main()
