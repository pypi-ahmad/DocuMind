from app.core.settings import settings
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider
from app.providers.gemini import GeminiProvider
from app.providers.anthropic import AnthropicProvider


def test_provider_names() -> None:
    assert OllamaProvider().provider_name == "ollama"
    assert OpenAIProvider().provider_name == "openai"
    assert GeminiProvider().provider_name == "gemini"
    assert AnthropicProvider().provider_name == "anthropic"


def test_ollama_is_configured_by_default() -> None:
    assert OllamaProvider().is_configured() is True


def test_providers_without_keys_are_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    assert OpenAIProvider().is_configured() is False
    assert GeminiProvider().is_configured() is False
    assert AnthropicProvider().is_configured() is False
