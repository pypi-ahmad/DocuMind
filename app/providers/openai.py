from typing import Any

from app.core.settings import settings
from app.providers.base import (
    BaseProvider,
    ProviderConfigurationError,
    ProviderGenerateResult,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.providers import ModelOption


class OpenAIProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "openai"

    def is_configured(self) -> bool:
        return bool(settings.openai_api_key)

    async def list_models(self, api_key: str | None = None) -> list[ModelOption]:
        resolved_api_key = self.require_key(api_key)
        payload = await self._get_json(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {resolved_api_key}"},
            auth_required=True,
        )
        models = payload.get("data")

        if not isinstance(models, list):
            raise ProviderUpstreamError("openai returned an invalid models response")

        normalized: list[ModelOption] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            model_id = str(model.get("id") or "").strip()
            if not model_id:
                continue

            normalized.append(
                ModelOption(
                    id=model_id,
                    display_name=model_id,
                    provider=self.provider_name,
                )
            )

        return normalized

    async def generate_text(
        self,
        model_name: str,
        prompt: str,
        api_key: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> ProviderGenerateResult:
        resolved_api_key = self.require_key(api_key)

        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AsyncOpenAI,
                AuthenticationError,
                PermissionDeniedError,
            )
        except ImportError as exc:
            raise ProviderConfigurationError("openai SDK is not installed") from exc

        request_body: dict[str, Any] = {
            "model": model_name,
            "input": prompt,
            "store": False,
        }
        if temperature is not None:
            request_body["temperature"] = temperature
        if max_output_tokens is not None:
            request_body["max_output_tokens"] = max_output_tokens

        try:
            async with AsyncOpenAI(
                api_key=resolved_api_key,
                timeout=settings.http_timeout_seconds,
            ) as client:
                response = await client.responses.create(**request_body)
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise ProviderUnauthorizedError("Invalid or unauthorized openai API key") from exc
        except APITimeoutError as exc:
            raise ProviderUpstreamError("openai request timed out") from exc
        except APIConnectionError as exc:
            raise ProviderUpstreamError("openai request failed") from exc
        except APIStatusError as exc:
            if exc.status_code in {401, 403}:
                raise ProviderUnauthorizedError("Invalid or unauthorized openai API key") from exc
            raise ProviderUpstreamError(
                f"openai upstream request failed with status {exc.status_code}"
            ) from exc

        usage = getattr(response, "usage", None)
        metadata = {
            key: value
            for key, value in {
                "response_id": getattr(response, "id", None),
                "status": getattr(response, "status", None),
            }.items()
            if value is not None
        }

        return ProviderGenerateResult(
            provider=self.provider_name,
            model_name=model_name,
            text=response.output_text or "",
            usage=self._build_usage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            ),
            metadata=metadata,
        )

    async def generate_embeddings(
        self,
        model_name: str,
        input_texts: list[str],
        api_key: str | None = None,
    ) -> dict[str, Any]:
        resolved_api_key = self.require_key(api_key)

        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AsyncOpenAI,
                AuthenticationError,
                PermissionDeniedError,
            )
        except ImportError as exc:
            raise ProviderConfigurationError("openai SDK is not installed") from exc

        try:
            async with AsyncOpenAI(
                api_key=resolved_api_key,
                timeout=settings.http_timeout_seconds,
            ) as client:
                response = await client.embeddings.create(
                    model=model_name,
                    input=input_texts,
                )
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise ProviderUnauthorizedError("Invalid or unauthorized openai API key") from exc
        except APITimeoutError as exc:
            raise ProviderUpstreamError("openai request timed out") from exc
        except APIConnectionError as exc:
            raise ProviderUpstreamError("openai request failed") from exc
        except APIStatusError as exc:
            if exc.status_code in {401, 403}:
                raise ProviderUnauthorizedError("Invalid or unauthorized openai API key") from exc
            raise ProviderUpstreamError(
                f"openai upstream request failed with status {exc.status_code}"
            ) from exc

        vectors = [
            {"index": item.index, "vector": item.embedding}
            for item in response.data
        ]

        usage = getattr(response, "usage", None)
        metadata: dict[str, Any] = {}
        if usage is not None:
            metadata["total_tokens"] = getattr(usage, "total_tokens", None)

        return {
            "provider": self.provider_name,
            "model_name": model_name,
            "vectors": vectors,
            "metadata": metadata,
        }