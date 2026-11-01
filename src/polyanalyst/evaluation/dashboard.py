"""Optional Streamlit rendering for evaluation summaries."""

from __future__ import annotations

from polyanalyst.evaluation.metrics import EvaluationSummary


def render_summary(summary: EvaluationSummary) -> None:
    """Render metrics without importing Streamlit at package import time."""

    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install polyanalyst[ui] to render the dashboard") from exc
    st.subheader("Evaluation")
    st.json(summary.metrics)
