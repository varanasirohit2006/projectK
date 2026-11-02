from pathlib import Path

from polyanalyst.config import Settings
from polyanalyst.evidence.repository import SQLiteEvidenceStore
from polyanalyst.llm.base import CallableLLM
from polyanalyst.llm.gemini import GeminiProvider
from polyanalyst.models import EvidenceItem, Finding, ResearchQuery, Source, SourceType
from polyanalyst.reporting.drafting import GeneratedReportNarrative, ReportGenerator


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(
            '{"executive_summary":"Gemini summary.",'
            '"risk_assessment":"Gemini risk assessment.",'
            '"uncertainty_notes":["The evidence set is limited."]}'
        )


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


def test_settings_detects_gemini_key_without_exposing_it(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    monkeypatch.delenv("POLYANALYST_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("POLYANALYST_MODEL_NAME", raising=False)

    settings = Settings.from_env()

    assert settings.model_provider == "gemini"
    assert settings.model_name == "gemma-4-31b-it"
    assert settings.gemini_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)


def test_gemini_provider_validates_structured_output() -> None:
    client = FakeClient()
    provider = GeminiProvider(api_key="test-secret", client=client)

    result = provider.generate_structured("Write a report.", GeneratedReportNarrative)

    assert result.executive_summary == "Gemini summary."
    assert client.models.calls[0]["model"] == "gemma-4-31b-it"
    assert client.models.calls[0]["config"]["response_mime_type"] == "application/json"


def test_report_generator_uses_llm_but_keeps_evidence_links(tmp_path: Path) -> None:
    def generate(_: str, schema):
        return schema(
            executive_summary="Generated summary.",
            risk_assessment="Generated risk assessment.",
            uncertainty_notes=[],
        )

    source = Source(
        title="Source",
        source_type=SourceType.WEB,
        url="https://example.com",
        content_hash="hash",
    )
    evidence = EvidenceItem(
        claim="Supplier lead times increased.",
        excerpt="Supplier lead times increased.",
        source_id=source.source_id,
        confidence=0.8,
    )
    with SQLiteEvidenceStore(tmp_path / "llm.db") as store:
        store.add_source(source)
        store.add_evidence(evidence)
        report = ReportGenerator(llm=CallableLLM(generate)).draft(
            ResearchQuery(question="What changed in lead times?"),
            [evidence],
            [Finding(agent_name="research", summary="One finding")],
            [],
            store,
            "run-1",
        )

    assert report.llm_used is True
    assert "Generated summary." in report.markdown
    assert evidence.evidence_id in report.markdown
