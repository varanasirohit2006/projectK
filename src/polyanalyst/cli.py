"""Command-line entry point for local demos and plan inspection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from polyanalyst.config import Settings
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.graph.checkpoints import RunRepository
from polyanalyst.graph.workflow import ResearchWorkflow
from polyanalyst.ingestion.documents import InMemoryDocumentStore
from polyanalyst.llm.factory import build_llm_provider
from polyanalyst.models import ResearchQuery, RiskLevel


def build_demo_workflow(
    database: str | Path,
) -> tuple[ResearchWorkflow, SQLiteEvidenceStore, RunRepository]:
    """Build an offline workflow with one private demonstration document."""

    evidence_store = SQLiteEvidenceStore(database)
    run_repository = RunRepository(database)
    documents = InMemoryDocumentStore()
    documents.add_text(
        "demo-operations-memo",
        "Operations memo",
        (
            "Supplier diversification, lead-time monitoring, and contingency inventory "
            "reduce operational disruption exposure."
        ),
        collection_id="demo",
    )
    settings = Settings.from_env()
    return (
        ResearchWorkflow(
            evidence_store,
            run_repository,
            document_store=documents,
            llm=build_llm_provider(settings),
        ),
        evidence_store,
        run_repository,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polyanalyst")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the offline research workflow")
    run_parser.add_argument("question")
    run_parser.add_argument("--database", default="data/polyanalyst.db")
    run_parser.add_argument("--approve-plan", action="store_true")
    run_parser.add_argument("--approve-high-risk", action="store_true")
    run_parser.add_argument(
        "--risk",
        choices=[level.value for level in RiskLevel],
        default="medium",
    )
    run_parser.add_argument("--export", type=Path)

    plan_parser = subparsers.add_parser("plan", help="create and print a plan")
    plan_parser.add_argument("question")
    plan_parser.add_argument("--database", default="data/polyanalyst.db")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    workflow, evidence_store, run_repository = build_demo_workflow(args.database)
    try:
        if args.command == "plan":
            query = ResearchQuery(question=args.question)
            result = workflow.run(query)
            print(json.dumps(result.state.model_dump(mode="json"), indent=2))
            return 0

        query = ResearchQuery(question=args.question, risk_level=args.risk)
        result = workflow.run(
            query,
            approve_plan=args.approve_plan,
            human_approval=True if args.approve_high_risk else None,
        )
        print(json.dumps({"run_id": result.run_id, "status": result.status.value}, indent=2))
        if result.state.clarification_questions:
            print("Clarification questions:")
            for question in result.state.clarification_questions:
                print(f"- {question}")
        if result.state.plan and result.status.value == "waiting_for_plan_approval":
            print("Plan approval is required. Re-run with --approve-plan.")
        if result.state.report_markdown:
            if args.export:
                args.export.parent.mkdir(parents=True, exist_ok=True)
                args.export.write_text(result.state.report_markdown, encoding="utf-8")
                print(f"Report written to {args.export}")
            else:
                print(result.state.report_markdown)
        return 0
    finally:
        evidence_store.close()
        run_repository.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
