from app.core.settings import settings
from app.providers.base import (
    BaseProvider,
    ProviderConfigurationError,
    ProviderGenerateResult,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.providers import ModelOption


class AnthropicProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "anthropic"

    def is_configured(self) -> bool:
        return bool(settings.anthropic_api_key)

    async def list_models(self, api_key: str | None = None) -> list[ModelOption]:
        resolved_api_key = self.require_key(api_key)
        payload = await self._get_json(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": resolved_api_key,
                "anthropic-version": "2023-06-01",
            },
            auth_required=True,
        )
        models = payload.get("data")

        if not isinstance(models, list):
            raise ProviderUpstreamError("anthropic returned an invalid models response")

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
                    display_name=str(model.get("display_name") or model_id),
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
            from anthropic import (
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AsyncAnthropic,
                AuthenticationError,
                PermissionDeniedError,
            )
        except ImportError as exc:
            raise ProviderConfigurationError("anthropic SDK is not installed") from exc

        request_body: dict[str, object] = {
            "model": model_name,
            "max_tokens": max_output_tokens or settings.llm_default_max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            request_body["temperature"] = temperature

        try:
            async with AsyncAnthropic(
                api_key=resolved_api_key,
                timeout=settings.http_timeout_seconds,
            ) as client:
                message = await client.messages.create(**request_body)
        except (AuthenticationError, PermissionDeniedError) as exc:
            raise ProviderUnauthorizedError("Invalid or unauthorized anthropic API key") from exc
        except APITimeoutError as exc:
            raise ProviderUpstreamError("anthropic request timed out") from exc
        except APIConnectionError as exc:
            raise ProviderUpstreamError("anthropic request failed") from exc
        except APIStatusError as exc:
            if exc.status_code in {401, 403}:
                raise ProviderUnauthorizedError("Invalid or unauthorized anthropic API key") from exc
            raise ProviderUpstreamError(
                f"anthropic upstream request failed with status {exc.status_code}"
            ) from exc

        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text" and hasattr(block, "text")
        )
        usage = getattr(message, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        metadata = {
            key: value
            for key, value in {
                "message_id": getattr(message, "id", None),
                "stop_reason": getattr(message, "stop_reason", None),
                "stop_sequence": getattr(message, "stop_sequence", None),
            }.items()
            if value is not None
        }

        return ProviderGenerateResult(
            provider=self.provider_name,
            model_name=model_name,
            text=text,
            usage=self._build_usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            metadata=metadata,
        )
