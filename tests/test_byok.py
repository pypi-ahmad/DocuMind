from fastapi.testclient import TestClient

from app.core.secrets import has_env_api_key, resolve_provider_api_key
from app.core.settings import Settings, settings
from app.main import app

client = TestClient(app)


# --- Unit tests for resolve_provider_api_key ---


def test_request_key_takes_priority_over_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "env-key")
    result = resolve_provider_api_key("openai", "request-key")
    assert result == "request-key"


def test_env_key_used_as_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "env-key")
    result = resolve_provider_api_key("openai", None)
    assert result == "env-key"


def test_empty_request_key_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "env-gemini")
    result = resolve_provider_api_key("gemini", "   ")
    assert result == "env-gemini"


def test_no_key_available_returns_none() -> None:
    result = resolve_provider_api_key("openai", None)
    assert result is None


def test_unknown_provider_returns_none() -> None:
    result = resolve_provider_api_key("unknown_provider", None)
    assert result is None


def test_ollama_request_key_passthrough() -> None:
    # ollama is not in the env key map so env fallback is None
    # but a request key is returned as-is (not blocked)
    result = resolve_provider_api_key("ollama", "some-key")
    assert result == "some-key"


def test_ollama_env_fallback_returns_none() -> None:
    result = resolve_provider_api_key("ollama", None)
    assert result is None


def test_whitespace_env_key_treated_as_absent(monkeypatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "   ")
    result = resolve_provider_api_key("anthropic", None)
    assert result is None


def test_settings_support_unprefixed_env_api_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-env-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-env-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-env-key")
    monkeypatch.delenv("DOCUMIND_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DOCUMIND_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DOCUMIND_ANTHROPIC_API_KEY", raising=False)

    loaded_settings = Settings(_env_file=None)

    assert loaded_settings.openai_api_key == "openai-env-key"
    assert loaded_settings.gemini_api_key == "gemini-env-key"
    assert loaded_settings.anthropic_api_key == "anthropic-env-key"


def test_settings_keep_prefixed_env_api_keys_compatible(monkeypatch) -> None:
    monkeypatch.setenv("DOCUMIND_OPENAI_API_KEY", "prefixed-openai-key")
    monkeypatch.setenv("DOCUMIND_GEMINI_API_KEY", "prefixed-gemini-key")
    monkeypatch.setenv("DOCUMIND_ANTHROPIC_API_KEY", "prefixed-anthropic-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    loaded_settings = Settings(_env_file=None)

    assert loaded_settings.openai_api_key == "prefixed-openai-key"
    assert loaded_settings.gemini_api_key == "prefixed-gemini-key"
    assert loaded_settings.anthropic_api_key == "prefixed-anthropic-key"


# --- Unit tests for has_env_api_key ---


def test_has_env_api_key_true(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "real-key")
    assert has_env_api_key("openai") is True


def test_has_env_api_key_false_when_empty() -> None:
    assert has_env_api_key("openai") is False


def test_has_env_api_key_false_for_ollama() -> None:
    assert has_env_api_key("ollama") is False


def test_has_env_api_key_false_for_unknown() -> None:
    assert has_env_api_key("unknown") is False


# --- GET /providers visibility tests ---


def test_providers_list_includes_byok_fields() -> None:
    response = client.get("/providers")
    assert response.status_code == 200
    providers = {p["provider"]: p for p in response.json()}

    assert providers["ollama"]["requires_api_key"] is False
    assert providers["ollama"]["supports_byok"] is False
    assert providers["ollama"]["has_env_key"] is False

    for name in ("openai", "gemini", "anthropic"):
        assert providers[name]["requires_api_key"] is True
        assert providers[name]["supports_byok"] is True


def test_providers_list_reflects_env_key_presence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    response = client.get("/providers")
    providers = {p["provider"]: p for p in response.json()}

    assert providers["openai"]["has_env_key"] is True
    assert providers["gemini"]["has_env_key"] is False
    assert providers["anthropic"]["has_env_key"] is False


# --- Route-level BYOK integration tests ---


def test_llm_generate_with_env_fallback_reaches_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "env-openai-key")

    response = client.post(
        "/llm/generate",
        json={
            "provider": "openai",
            "model_name": "gpt-4",
            "prompt": "hello",
        },
    )
    # env key is used; the fake key triggers auth or upstream, not "requires api_key"
    assert response.status_code in {401, 502}
    assert "requires api_key" not in response.json().get("detail", "")


def test_llm_generate_request_key_overrides_env(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "env-openai-key")

    response = client.post(
        "/llm/generate",
        json={
            "provider": "openai",
            "model_name": "gpt-4",
            "prompt": "hello",
            "api_key": "request-override-key",
        },
    )
    # request key used; the fake key triggers auth or upstream
    assert response.status_code in {401, 502}


def test_llm_generate_no_key_returns_400() -> None:
    response = client.post(
        "/llm/generate",
        json={
            "provider": "openai",
            "model_name": "gpt-4",
            "prompt": "hello",
        },
    )
    assert response.status_code == 400
    assert "requires api_key" in response.json()["detail"]


def test_provider_models_with_env_fallback_reaches_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "env-gemini-key")

    response = client.post(
        "/providers/gemini/models",
        json={},
    )
    # env key used; fake key triggers auth or upstream, not "requires api_key"
    assert response.status_code in {401, 502}
