import pytest
from fastapi.testclient import TestClient

from app.core.model_manager import model_manager
from app.main import app
from app.providers.base import ProviderGenerateResult, ProviderUpstreamError
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider
from app.services.ocr_postprocess import build_postprocess_prompt

client = TestClient(app)

SAMPLE_OCR_RESULT: dict = {
    "engine": "deepseek-ocr",
    "text": "  Inv oice  #12345\nDate: 2026-01-15\n\nTotal:  $1,250.00  ",
    "normalized_text": "Invoice #12345\nDate: 2026-01-15\nTotal: $1,250.00",
    "structured": {
        "sections": [
            {"heading": "Header", "body": "Invoice #12345"},
        ],
        "paragraphs": ["Invoice #12345", "Date: 2026-01-15", "Total: $1,250.00"],
    },
    "confidence": 0.92,
    "metadata": {},
}


# ---------- build_postprocess_prompt unit tests ----------


class TestBuildPostprocessPrompt:
    def test_cleanup_prompt_contains_instruction_and_text(self) -> None:
        prompt = build_postprocess_prompt(SAMPLE_OCR_RESULT, "cleanup")
        assert "cleaner, human-readable version" in prompt
        assert "Do not invent" in prompt
        assert "Invoice #12345" in prompt

    def test_summary_prompt_contains_instruction_and_text(self) -> None:
        prompt = build_postprocess_prompt(SAMPLE_OCR_RESULT, "summary")
        assert "concise, factual summary" in prompt
        assert "Do not infer" in prompt
        assert "Invoice #12345" in prompt

    def test_extract_key_fields_prompt_contains_instruction_and_text(self) -> None:
        prompt = build_postprocess_prompt(SAMPLE_OCR_RESULT, "extract_key_fields")
        assert "key fields" in prompt
        assert "Field: Value" in prompt
        assert "Invoice #12345" in prompt

    def test_prefers_normalized_text(self) -> None:
        prompt = build_postprocess_prompt(SAMPLE_OCR_RESULT, "cleanup")
        assert "Invoice #12345" in prompt
        assert "Inv oice" not in prompt

    def test_falls_back_to_raw_text(self) -> None:
        result = {"text": "raw OCR text here"}
        prompt = build_postprocess_prompt(result, "cleanup")
        assert "raw OCR text here" in prompt

    def test_includes_structured_sections(self) -> None:
        prompt = build_postprocess_prompt(SAMPLE_OCR_RESULT, "summary")
        assert "[Section: Header]" in prompt

    def test_empty_ocr_result_degrades_gracefully(self) -> None:
        prompt = build_postprocess_prompt({}, "cleanup")
        assert "No usable text" in prompt

    def test_invalid_task_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported task"):
            build_postprocess_prompt(SAMPLE_OCR_RESULT, "translate")


# ---------- POST /ocr/postprocess route tests ----------


def _make_fake_generate(provider_name: str):
    async def fake_generate_text(
        self,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, object]:
        return {
            "provider": provider_name,
            "model_name": model_name,
            "text": f"Fake {provider_name} output",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "metadata": {},
        }

    return fake_generate_text


def test_postprocess_cleanup_with_ollama(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict:
        events.append(("activate", provider, model_name))
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OllamaProvider, "generate_text", _make_fake_generate("ollama"))

    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "cleanup",
            "provider": "ollama",
            "model_name": "llama3.2",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task"] == "cleanup"
    assert body["provider"] == "ollama"
    assert body["model_name"] == "llama3.2"
    assert body["output_text"] == "Fake ollama output"
    assert body["usage"]["total_tokens"] == 15
    assert ("activate", "ollama", "llama3.2") in events
    assert ("busy",) in events
    assert ("idle",) in events


def test_postprocess_summary_with_openai(monkeypatch) -> None:
    events: list[tuple] = []

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OpenAIProvider, "generate_text", _make_fake_generate("openai"))

    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "summary",
            "provider": "openai",
            "model_name": "gpt-5",
            "api_key": "test-key",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task"] == "summary"
    assert body["provider"] == "openai"
    assert body["output_text"] == "Fake openai output"
    assert ("busy",) in events
    assert ("idle",) in events


def test_postprocess_invalid_task_returns_400() -> None:
    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "translate",
            "provider": "ollama",
            "model_name": "llama3.2",
        },
    )

    assert response.status_code == 422


def test_postprocess_missing_api_key_for_cloud_returns_400(monkeypatch) -> None:
    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "cleanup",
            "provider": "openai",
            "model_name": "gpt-5",
        },
    )

    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


def test_postprocess_upstream_error_returns_502(monkeypatch) -> None:
    async def fake_activate(provider: str, model_name: str) -> dict:
        return {}

    async def fake_generate_text(self, model_name, prompt, **kwargs):
        raise ProviderUpstreamError("ollama request timed out")

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "extract_key_fields",
            "provider": "ollama",
            "model_name": "llama3.2",
        },
    )

    assert response.status_code == 502
    assert "timed out" in response.json()["detail"]


def test_postprocess_marks_idle_on_error(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict:
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    async def fake_generate_text(self, model_name, prompt, **kwargs):
        raise ProviderUpstreamError("boom")

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "cleanup",
            "provider": "ollama",
            "model_name": "llama3.2",
        },
    )

    assert response.status_code == 502
    assert ("busy",) in events
    assert ("idle",) in events


def test_postprocess_cloud_provider_skips_activation(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict:
        events.append(("activate",))
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OpenAIProvider, "generate_text", _make_fake_generate("openai"))

    response = client.post(
        "/ocr/postprocess",
        json={
            "ocr_result": SAMPLE_OCR_RESULT,
            "task": "extract_key_fields",
            "provider": "openai",
            "model_name": "gpt-5",
            "api_key": "sk-test",
        },
    )

    assert response.status_code == 200
    assert ("activate",) not in events
    assert ("busy",) in events
    assert ("idle",) in events
