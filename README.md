# PolyAnalyst

PolyAnalyst is a typed, evidence-centric multi-agent research platform. It
turns a complex question into a reviewable plan, runs specialist research
tasks, stores claims with provenance, and produces a citation-backed report.

## Current implementation

- Supervisor-generated DAG with plan preview and approval;
- Research, RAG, data analyst, risk/critic, reporter, and reviewer agents;
- parallel independent tasks with retries and resumable SQLite checkpoints;
- SQLite evidence store with source provenance and claim-to-evidence links;
- source deduplication, quality/freshness scores, contradictions, and uncertainty;
- human approval for high-risk plans;
- MCP-shaped tool discovery and web-search adapter;
- read-only SQL, CSV-only analysis, filesystem policy, and prompt-injection flags;
- Recall@3, faithfulness, citation coverage, and answer-correctness metrics;
- offline demo provider so the complete flow runs without API keys;
- optional LangGraph, ChromaDB, MCP SDK, Streamlit, and ReportLab adapters.

Optional integrations are kept behind extras so the core remains easy to run:

```text
pip install -e ".[dev,workflow,ui,mcp,vector,pdf,gemini]"
```

## Development

```text
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
ruff check .
```

## CLI demo

Create a plan without executing it:

```text
python -m polyanalyst plan "Analyze supply chain resilience"
```

Approve and execute the offline workflow:

```text
python -m polyanalyst run "Analyze supply chain resilience" --approve-plan --export data/report.md
```

For the interactive interface, install the UI extra and run:

```text
streamlit run src/polyanalyst/ui/streamlit_app.py
```

## Architecture

Agents communicate through typed workflow state and the evidence store rather
than passing unstructured messages. External capabilities implement the
`SearchProvider` or MCP tool contract. Retrieved web pages and documents are
treated as untrusted evidence, while data analysis is restricted to bounded
CSV statistics or read-only SQL.

Runtime data is written to `data/` and is intentionally ignored by Git. Copy
`.env.example` to `.env` when configuring a real provider. API-specific model
adapters can be added without changing the domain models or workflow.

## Gemini provider

The official `google-genai` SDK is integrated behind the provider contract.
Keep the key in the environment and never commit it:

PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-key"
$env:POLYANALYST_MODEL_PROVIDER = "gemini"
$env:POLYANALYST_MODEL_NAME = "gemini-2.5-flash"
```

Alternatively, put the same variables in a local `.env` file. `.env` is
ignored by Git and is loaded automatically at startup.

Then run the normal CLI or Streamlit flow. Gemini generates the bounded report
narrative from the collected evidence; deterministic citation linking and
review remain active. If no provider is configured, the offline demo behavior
continues to work.
