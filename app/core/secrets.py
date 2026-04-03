from app.core.settings import settings

_ENV_KEY_MAP: dict[str, str] = {
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "anthropic": "anthropic_api_key",
}


def resolve_provider_api_key(provider: str, request_api_key: str | None) -> str | None:
    if request_api_key is not None:
        stripped = request_api_key.strip()
        if stripped:
            return stripped

    attr_name = _ENV_KEY_MAP.get(provider.strip().lower())
    if attr_name is None:
        return None

    env_value = getattr(settings, attr_name, "")
    if isinstance(env_value, str) and env_value.strip():
        return env_value.strip()

    return None


def has_env_api_key(provider: str) -> bool:
    attr_name = _ENV_KEY_MAP.get(provider.strip().lower())
    if attr_name is None:
        return False

    env_value = getattr(settings, attr_name, "")
    return isinstance(env_value, str) and bool(env_value.strip())
