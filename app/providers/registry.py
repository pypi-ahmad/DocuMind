from typing import Final

from app.providers.anthropic import AnthropicProvider
from app.providers.base import BaseProvider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider

PROVIDER_FACTORIES: Final[dict[str, type[BaseProvider]]] = {
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
}

API_KEY_REQUIRED: Final[set[str]] = {"openai", "gemini", "anthropic"}