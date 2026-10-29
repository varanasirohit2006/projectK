"""Optional LangGraph adapter.

The core workflow remains runnable without optional dependencies. When
LangGraph is installed, this adapter exposes the same plan approval boundary
as a graph for projects that want native LangGraph execution/checkpointing.
"""

from __future__ import annotations

from typing import TypedDict

from polyanalyst.graph.workflow import ResearchWorkflow


class LangGraphState(TypedDict, total=False):
    run_id: str
    approve_plan: bool
    human_approval: bool | None


def build_langgraph(workflow: ResearchWorkflow):
    """Build a small LangGraph wrapper around the durable workflow.

    Importing this function does not require LangGraph; calling it produces a
    clear installation error when the optional extra is absent.
    """

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError("Install polyanalyst[workflow] to use LangGraph") from exc

    def resume_node(state: LangGraphState) -> LangGraphState:
        result = workflow.resume(
            state["run_id"],
            approve_plan=state.get("approve_plan", False),
            human_approval=state.get("human_approval"),
        )
        return {
            "run_id": result.run_id,
            "approve_plan": True,
            "human_approval": state.get("human_approval"),
        }

    graph = StateGraph(LangGraphState)
    graph.add_node("resume", resume_node)
    graph.add_edge(START, "resume")
    graph.add_edge("resume", END)
    return graph.compile()
