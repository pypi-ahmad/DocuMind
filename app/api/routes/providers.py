from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, status

from app.core.secrets import has_env_api_key, resolve_provider_api_key
from app.providers.base import (
    ProviderConfigurationError,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.common import ErrorResponse
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES
from app.schemas.providers import ProviderDescriptor, ProviderModelsRequest, ProviderModelsResponse

router = APIRouter(prefix="/providers", tags=["providers"])

_PROVIDER_MODELS_EXAMPLES = {
    "byok": {
        "summary": "List models with a BYOK request",
        "value": {
            "api_key": "sk-demo",
        },
    }
}


@router.get(
    "",
    response_model=list[ProviderDescriptor],
    summary="List providers",
    description="Return supported LLM providers and simple capability flags for UI discovery.",
)
def list_providers() -> list[ProviderDescriptor]:
    return [
        ProviderDescriptor(
            provider=name,
            requires_api_key=name in API_KEY_REQUIRED,
            supports_byok=name in API_KEY_REQUIRED,
            has_env_key=has_env_api_key(name),
        )
        for name in PROVIDER_FACTORIES
    ]


@router.post(
    "/{provider}/models",
    response_model=ProviderModelsResponse,
    summary="List provider models",
    description="Return the model options exposed by the selected provider.",
    responses={
        400: {"model": ErrorResponse, "description": "Provider configuration error."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        404: {"model": ErrorResponse, "description": "Provider not found."},
        502: {"model": ErrorResponse, "description": "Upstream provider error."},
    },
)
async def list_provider_models(
    provider: Annotated[
        str,
        Path(description="Provider name to inspect.", examples=["openai"]),
    ],
    payload: Annotated[
        ProviderModelsRequest | None,
        Body(openapi_examples=_PROVIDER_MODELS_EXAMPLES),
    ] = None,
) -> ProviderModelsResponse:
    provider_name = provider.lower()
    provider_factory = PROVIDER_FACTORIES.get(provider_name)

    if provider_factory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    provider_client = provider_factory()
    api_key = payload.api_key.strip() if payload and payload.api_key else None
    resolved_key = resolve_provider_api_key(provider_name, api_key)
    if provider_name in API_KEY_REQUIRED and not resolved_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider_name} requires api_key",
        )

    try:
        models = await provider_client.list_models(api_key=api_key)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ProviderUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return ProviderModelsResponse(provider=provider_client.provider_name, models=models)