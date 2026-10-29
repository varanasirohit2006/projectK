"""Evidence-linked Markdown report generation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.models import (
    Contradiction,
    EvidenceItem,
    Finding,
    ReportClaim,
    ResearchQuery,
)


class DraftReport(BaseModel):
    """A report plus the exact claims used to construct it."""

    title: str
    markdown: str
    claims: list[ReportClaim] = Field(default_factory=list)


class ReportGenerator:
    """Turn normalized evidence into a readable, traceable report."""

    def draft(
        self,
        query: ResearchQuery,
        evidence: list[EvidenceItem],
        findings: list[Finding],
        contradictions: list[Contradiction],
        store: SQLiteEvidenceStore,
        run_id: str,
    ) -> DraftReport:
        claims: list[ReportClaim] = []
        for item in evidence:
            claim = ReportClaim(
                text=item.claim,
                evidence_ids=[item.evidence_id],
                supported=True,
                confidence=item.confidence,
            )
            store.add_claim(claim, run_id=run_id)
            claims.append(claim)

        title = f"Research report: {query.question}"
        lines = [
            f"# {title}",
            "",
            "> This report was generated from structured evidence and reviewed "
            "for citation coverage.",
            "",
            "## Executive summary",
            "",
        ]
        if findings:
            lines.extend(f"- {finding.summary}" for finding in findings)
        else:
            lines.append("- No specialist findings were produced.")

        lines.extend(["", "## Evidence-backed findings", ""])
        if claims:
            for number, claim in enumerate(claims, start=1):
                lines.append(f"{number}. {claim.text} [Evidence: `{claim.evidence_ids[0]}`]")
        else:
            lines.append("No evidence was available for this question.")

        lines.extend(["", "## Contradictions and uncertainty", ""])
        if contradictions:
            for contradiction in contradictions:
                lines.append(f"- **Conflict:** {contradiction.claim_a}")
                lines.append(f"  - **Different source:** {contradiction.claim_b}")
                lines.append(f"  - **Resolution:** {contradiction.resolution}")
        else:
            lines.append("No explicit contradictory directional claims were detected.")

        lines.extend(["", "## Methodology", "", f"- Question: {query.question}"])
        if query.geography:
            lines.append(f"- Geography: {query.geography}")
        if query.time_period:
            lines.append(f"- Time period: {query.time_period}")

        lines.extend(["", "## Evidence appendix", ""])
        if evidence:
            for item in evidence:
                lines.append(
                    f"- `{item.evidence_id}` — {item.excerpt} "
                    f"(source `{item.source_id}`, confidence {item.confidence:.2f})"
                )
        else:
            lines.append("- No evidence items were collected.")

        return DraftReport(title=title, markdown="\n".join(lines) + "\n", claims=claims)

    def revise(self, draft: DraftReport, instructions: list[str]) -> DraftReport:
        """Add transparent review notes instead of silently changing claims."""

        if not instructions:
            return draft
        notes = ["", "## Reviewer notes", ""]
        notes.extend(f"- {instruction}" for instruction in instructions)
        markdown = draft.markdown.rstrip() + "\n" + "\n".join(notes) + "\n"
        return draft.model_copy(update={"markdown": markdown})
