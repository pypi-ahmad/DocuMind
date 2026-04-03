from fastapi.testclient import TestClient

from app.core.model_manager import model_manager
from app.main import app
from app.providers.base import ProviderUpstreamError
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider

client = TestClient(app)


def test_llm_generate_invalid_provider_returns_404() -> None:
    response = client.post(
        "/llm/generate",
        json={
            "provider": "unknown",
            "model_name": "test-model",
            "prompt": "Hello",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Provider not found"


def test_llm_generate_requires_api_key_for_openai() -> None:
    response = client.post(
        "/llm/generate",
        json={
            "provider": "openai",
            "model_name": "gpt-5",
            "prompt": "Hello",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "openai requires api_key"


def test_llm_generate_ollama_activates_model_and_returns_response(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict[str, str | bool | None]:
        events.append(("activate", provider, model_name))
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    async def fake_generate_text(
        self: OllamaProvider,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, object]:
        events.append(("generate", model_name, prompt, api_key, temperature, max_output_tokens))
        return {
            "provider": "ollama",
            "model_name": model_name,
            "text": "Synthetic Ollama output",
            "usage": {
                "input_tokens": 12,
                "output_tokens": 5,
                "total_tokens": 17,
            },
            "metadata": {"done_reason": "stop"},
        }

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/llm/generate",
        json={
            "provider": "ollama",
            "model_name": "llama3.2",
            "prompt": "Summarize this document.",
            "temperature": 0.1,
            "max_output_tokens": 128,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "ollama",
        "model_name": "llama3.2",
        "text": "Synthetic Ollama output",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 5,
            "total_tokens": 17,
        },
        "metadata": {"done_reason": "stop"},
    }
    assert events == [
        ("activate", "ollama", "llama3.2"),
        ("busy",),
        ("generate", "llama3.2", "Summarize this document.", None, 0.1, 128),
        ("idle",),
    ]


def test_llm_generate_cloud_provider_skips_activation(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict[str, str | bool | None]:
        events.append(("activate", provider, model_name))
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    async def fake_generate_text(
        self: OpenAIProvider,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, object]:
        events.append(("generate", model_name, prompt, api_key, temperature, max_output_tokens))
        return {
            "provider": "openai",
            "model_name": model_name,
            "text": "Synthetic OpenAI output",
            "usage": {
                "input_tokens": 20,
                "output_tokens": 8,
                "total_tokens": 28,
            },
            "metadata": {"response_id": "resp_123"},
        }

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OpenAIProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/llm/generate",
        json={
            "provider": "openai",
            "model_name": "gpt-5",
            "prompt": "Extract the key clauses.",
            "api_key": "test-key",
            "temperature": 0.2,
            "max_output_tokens": 256,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "openai",
        "model_name": "gpt-5",
        "text": "Synthetic OpenAI output",
        "usage": {
            "input_tokens": 20,
            "output_tokens": 8,
            "total_tokens": 28,
        },
        "metadata": {"response_id": "resp_123"},
    }
    assert events == [
        ("busy",),
        ("generate", "gpt-5", "Extract the key clauses.", "test-key", 0.2, 256),
        ("idle",),
    ]


def test_llm_generate_marks_idle_on_upstream_error(monkeypatch) -> None:
    events: list[tuple] = []

    async def fake_activate(provider: str, model_name: str) -> dict[str, str | bool | None]:
        events.append(("activate", provider, model_name))
        return {}

    def fake_mark_busy() -> None:
        events.append(("busy",))

    def fake_mark_idle() -> None:
        events.append(("idle",))

    async def fake_generate_text(
        self: OllamaProvider,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> dict[str, object]:
        events.append(("generate", model_name, prompt, api_key, temperature, max_output_tokens))
        raise ProviderUpstreamError("ollama request timed out")

    monkeypatch.setattr(model_manager, "activate", fake_activate)
    monkeypatch.setattr(model_manager, "mark_busy", fake_mark_busy)
    monkeypatch.setattr(model_manager, "mark_idle", fake_mark_idle)
    monkeypatch.setattr(OllamaProvider, "generate_text", fake_generate_text)

    response = client.post(
        "/llm/generate",
        json={
            "provider": "ollama",
            "model_name": "llama3.2",
            "prompt": "Summarize this document.",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "ollama request timed out"
    assert events == [
        ("activate", "ollama", "llama3.2"),
        ("busy",),
        ("generate", "llama3.2", "Summarize this document.", None, None, None),
        ("idle",),
    ]