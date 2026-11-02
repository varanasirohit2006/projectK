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
    columns = st.columns(max(len(summary.metrics), 1))
    for column, (name, value) in zip(columns, summary.metrics.items(), strict=False):
        column.metric(name.replace("_", " ").title(), f"{value:.0%}")
    for name, value in summary.metrics.items():
        st.progress(value, text=name.replace("_", " ").title())
