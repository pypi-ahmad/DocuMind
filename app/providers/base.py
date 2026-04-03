from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.settings import settings
from app.schemas.providers import ModelOption


class ProviderError(Exception):
    pass


class ProviderConfigurationError(ProviderError):
    pass


class ProviderUnauthorizedError(ProviderError):
    pass


class ProviderUpstreamError(ProviderError):
    pass


class ProviderNotImplementedError(ProviderError):
    pass


@dataclass(slots=True)
class ProviderGenerateResult:
    provider: str
    model_name: str
    text: str
    usage: dict[str, int | None] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "text": self.text,
            "usage": self.usage,
            "metadata": self.metadata,
        }


class BaseProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def list_models(self, api_key: str | None = None) -> list[ModelOption]: ...

    @abstractmethod
    async def generate_text(
        self,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> ProviderGenerateResult | dict[str, Any]: ...

    async def generate_embeddings(
        self,
        model_name: str,
        input_texts: list[str],
        api_key: str | None = None,
    ) -> dict[str, Any]:
        raise ProviderNotImplementedError(
            f"{self.provider_name} does not support embeddings"
        )

    def _resolve_api_key(self, api_key: str | None, configured_api_key: str) -> str | None:
        resolved = api_key if api_key is not None else configured_api_key
        normalized = resolved.strip()
        return normalized or None

    def _require_api_key(self, api_key: str | None, configured_api_key: str) -> str:
        resolved = self._resolve_api_key(api_key, configured_api_key)
        if not resolved:
            raise ProviderConfigurationError(f"{self.provider_name} requires api_key")
        return resolved

    def resolve_key(self, request_api_key: str | None) -> str | None:
        from app.core.secrets import resolve_provider_api_key
        return resolve_provider_api_key(self.provider_name, request_api_key)

    def require_key(self, request_api_key: str | None) -> str:
        resolved = self.resolve_key(request_api_key)
        if not resolved:
            raise ProviderConfigurationError(f"{self.provider_name} requires api_key")
        return resolved

    @staticmethod
    def _build_usage(
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> dict[str, int | None]:
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        auth_required: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        client_timeout = timeout_seconds or settings.http_timeout_seconds

        try:
            async with httpx.AsyncClient(timeout=client_timeout) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise ProviderUpstreamError(f"{self.provider_name} request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUpstreamError(f"{self.provider_name} request failed") from exc

        if auth_required and response.status_code in {400, 401, 403}:
            raise ProviderUnauthorizedError(f"Invalid or unauthorized {self.provider_name} API key")

        if response.is_error:
            raise ProviderUpstreamError(
                f"{self.provider_name} upstream request failed with status {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderUpstreamError(f"{self.provider_name} returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise ProviderUpstreamError(f"{self.provider_name} returned an invalid response shape")

        return payload

    async def _get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        auth_required: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            url,
            headers=headers,
            params=params,
            auth_required=auth_required,
            timeout_seconds=timeout_seconds,
        )

    async def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        auth_required: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            url,
            headers=headers,
            params=params,
            json=json,
            auth_required=auth_required,
            timeout_seconds=timeout_seconds,
        )
