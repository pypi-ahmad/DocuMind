from typing import Any

from app.core.settings import settings
from app.providers.base import BaseProvider, ProviderGenerateResult, ProviderUpstreamError
from app.schemas.providers import ModelOption


class OllamaProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_configured(self) -> bool:
        return bool(settings.ollama_base_url)

    async def list_models(self, api_key: str | None = None) -> list[ModelOption]:
        payload = await self._get_json(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
        models = payload.get("models")

        if not isinstance(models, list):
            raise ProviderUpstreamError("ollama returned an invalid models response")

        normalized: list[ModelOption] = []
        for model in models:
            if not isinstance(model, dict):
                continue

            model_id = str(model.get("model") or model.get("name") or "").strip()
            if not model_id:
                continue

            normalized.append(
                ModelOption(
                    id=model_id,
                    display_name=str(model.get("name") or model_id),
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
        request_body: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": settings.ollama_keep_alive,
        }

        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens
        if options:
            request_body["options"] = options

        payload = await self._post_json(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json=request_body,
            timeout_seconds=settings.ollama_http_timeout_seconds,
        )

        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise ProviderUpstreamError("ollama returned an invalid generation response")

        metadata = {
            key: value
            for key, value in {
                "done": payload.get("done"),
                "done_reason": payload.get("done_reason"),
                "total_duration": payload.get("total_duration"),
                "load_duration": payload.get("load_duration"),
                "prompt_eval_duration": payload.get("prompt_eval_duration"),
                "eval_duration": payload.get("eval_duration"),
            }.items()
            if value is not None
        }

        return ProviderGenerateResult(
            provider=self.provider_name,
            model_name=model_name,
            text=response_text,
            usage=self._build_usage(
                input_tokens=payload.get("prompt_eval_count"),
                output_tokens=payload.get("eval_count"),
            ),
            metadata=metadata,
        )

    async def generate_embeddings(
        self,
        model_name: str,
        input_texts: list[str],
        api_key: str | None = None,
    ) -> dict[str, Any]:
        base_url = settings.ollama_base_url.rstrip("/")

        vectors: list[dict[str, Any]] = []
        for idx, text in enumerate(input_texts):
            payload = await self._post_json(
                f"{base_url}/api/embed",
                json={"model": model_name, "input": text},
                timeout_seconds=settings.ollama_http_timeout_seconds,
            )

            embeddings = payload.get("embeddings")
            if not isinstance(embeddings, list) or not embeddings:
                raise ProviderUpstreamError("ollama returned an invalid embeddings response")

            vectors.append({"index": idx, "vector": embeddings[0]})

        return {
            "provider": self.provider_name,
            "model_name": model_name,
            "vectors": vectors,
            "metadata": {},
        }
