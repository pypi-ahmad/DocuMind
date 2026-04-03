from typing import Any

import httpx

from app.core.settings import settings
from app.providers.base import (
    BaseProvider,
    ProviderConfigurationError,
    ProviderGenerateResult,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.providers import ModelOption


class GeminiProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_configured(self) -> bool:
        return bool(settings.gemini_api_key)

    async def list_models(self, api_key: str | None = None) -> list[ModelOption]:
        resolved_api_key = self.require_key(api_key)
        payload = await self._get_json(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": resolved_api_key},
            auth_required=True,
        )
        models = payload.get("models")

        if not isinstance(models, list):
            raise ProviderUpstreamError("gemini returned an invalid models response")

        normalized: list[ModelOption] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            raw_name = str(model.get("name") or "").strip()
            model_id = raw_name.removeprefix("models/")
            if not model_id:
                continue

            normalized.append(
                ModelOption(
                    id=model_id,
                    display_name=str(model.get("displayName") or model_id),
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
            from google import genai
            from google.genai import errors
        except ImportError as exc:
            raise ProviderConfigurationError("google-genai SDK is not installed") from exc

        request_config: dict[str, float | int] = {}
        if temperature is not None:
            request_config["temperature"] = temperature
        if max_output_tokens is not None:
            request_config["max_output_tokens"] = max_output_tokens

        try:
            async with genai.Client(
                api_key=resolved_api_key,
                http_options={
                    "api_version": "v1",
                    "timeout": int(settings.http_timeout_seconds * 1000),
                },
            ).aio as client:
                response = await client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=request_config or None,
                )
        except httpx.TimeoutException as exc:
            raise ProviderUpstreamError("gemini request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUpstreamError("gemini request failed") from exc
        except errors.ClientError as exc:
            error_message = (getattr(exc, "message", None) or "").lower()
            if getattr(exc, "code", None) in {401, 403} or "api key" in error_message:
                raise ProviderUnauthorizedError("Invalid or unauthorized gemini API key") from exc
            raise ProviderUpstreamError(
                f"gemini upstream request failed with status {getattr(exc, 'code', 'unknown')}"
            ) from exc
        except errors.ServerError as exc:
            raise ProviderUpstreamError(
                f"gemini upstream request failed with status {getattr(exc, 'code', 'unknown')}"
            ) from exc

        usage_metadata = getattr(response, "usage_metadata", None)
        finish_reason = None
        candidates = getattr(response, "candidates", None)
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
            if finish_reason is not None and not isinstance(finish_reason, str):
                finish_reason = getattr(finish_reason, "name", str(finish_reason))

        metadata = {
            key: value
            for key, value in {
                "response_id": getattr(response, "response_id", None),
                "model_version": getattr(response, "model_version", None),
                "finish_reason": finish_reason,
            }.items()
            if value is not None
        }

        return ProviderGenerateResult(
            provider=self.provider_name,
            model_name=model_name,
            text=response.text or "",
            usage=self._build_usage(
                input_tokens=getattr(usage_metadata, "prompt_token_count", None),
                output_tokens=(
                    getattr(usage_metadata, "candidates_token_count", None)
                    or getattr(usage_metadata, "response_token_count", None)
                ),
                total_tokens=getattr(usage_metadata, "total_token_count", None),
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
            from google import genai
            from google.genai import errors
        except ImportError as exc:
            raise ProviderConfigurationError("google-genai SDK is not installed") from exc

        try:
            async with genai.Client(
                api_key=resolved_api_key,
                http_options={
                    "api_version": "v1beta",
                    "timeout": int(settings.http_timeout_seconds * 1000),
                },
            ).aio as client:
                response = await client.models.embed_content(
                    model=model_name,
                    contents=input_texts,
                )
        except httpx.TimeoutException as exc:
            raise ProviderUpstreamError("gemini request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderUpstreamError("gemini request failed") from exc
        except errors.ClientError as exc:
            error_message = (getattr(exc, "message", None) or "").lower()
            if getattr(exc, "code", None) in {401, 403} or "api key" in error_message:
                raise ProviderUnauthorizedError("Invalid or unauthorized gemini API key") from exc
            raise ProviderUpstreamError(
                f"gemini upstream request failed with status {getattr(exc, 'code', 'unknown')}"
            ) from exc
        except errors.ServerError as exc:
            raise ProviderUpstreamError(
                f"gemini upstream request failed with status {getattr(exc, 'code', 'unknown')}"
            ) from exc

        embeddings = getattr(response, "embeddings", None)
        if not isinstance(embeddings, list):
            raise ProviderUpstreamError("gemini returned an invalid embeddings response")

        vectors = [
            {"index": idx, "vector": list(getattr(emb, "values", []))}
            for idx, emb in enumerate(embeddings)
        ]

        return {
            "provider": self.provider_name,
            "model_name": model_name,
            "vectors": vectors,
            "metadata": {},
        }