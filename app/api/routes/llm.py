from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.core.model_manager import model_manager
from app.core.secrets import resolve_provider_api_key
from app.providers.base import (
    ProviderConfigurationError,
    ProviderGenerateResult,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.common import ErrorResponse
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES
from app.schemas.llm import LLMGenerateRequest, LLMGenerateResponse

router = APIRouter(prefix="/llm", tags=["llm"])

_LLM_GENERATE_EXAMPLES = {
    "generate": {
        "summary": "Generate a grounded summary",
        "value": {
            "provider": "ollama",
            "model_name": "llama3",
            "prompt": "Summarize the invoice in one sentence.",
            "temperature": 0,
            "max_output_tokens": 128,
        },
    }
}


@router.post(
    "/generate",
    response_model=LLMGenerateResponse,
    summary="Generate text",
    description="Generate text from the selected provider and model using the supplied prompt.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid provider configuration or missing API key."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        404: {"model": ErrorResponse, "description": "Provider not found."},
        502: {"model": ErrorResponse, "description": "Provider upstream failure."},
    },
)
async def generate_text(
    payload: Annotated[LLMGenerateRequest, Body(openapi_examples=_LLM_GENERATE_EXAMPLES)],
) -> LLMGenerateResponse:
    provider_name = payload.provider.strip().lower()
    provider_factory = PROVIDER_FACTORIES.get(provider_name)

    if provider_factory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    provider_client = provider_factory()
    model_name = payload.model_name.strip()
    api_key = payload.api_key.strip() if payload.api_key else None

    resolved_key = resolve_provider_api_key(provider_name, api_key)
    if provider_name in API_KEY_REQUIRED and not resolved_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider_name} requires api_key",
        )

    if provider_name == "ollama":
        await model_manager.activate(provider_name, model_name)

    model_manager.mark_busy()
    try:
        result = await provider_client.generate_text(
            model_name=model_name,
            prompt=payload.prompt,
            api_key=api_key,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
        )
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ProviderUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        model_manager.mark_idle()

    if isinstance(result, ProviderGenerateResult):
        return LLMGenerateResponse(**result.to_dict())

    return LLMGenerateResponse(**result)