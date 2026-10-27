# PolyAnalyst

PolyAnalyst is a typed, evidence-centric multi-agent research platform. It
turns a complex question into a reviewable plan, runs specialist research
tasks, stores claims with provenance, and produces a citation-backed report.

## Current implementation

The first implementation slice includes:

- typed research, plan, task, source, evidence, review, approval, and run models;
- a SQLite evidence store with claim-to-evidence links;
- durable run events and workflow checkpoints;
- dependency-free agent interfaces suitable for MCP or hosted model adapters;
- an offline demo provider so the complete flow can be tested without API keys.

Optional integrations are kept behind extras so the core remains easy to run:

```text
pip install -e ".[dev,workflow,ui,mcp]"
```

## Development

```text
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

Runtime data is written to `data/` and is intentionally ignored by Git. Copy
`.env.example` to `.env` when configuring a real provider.
