from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.providers.base import (
    ProviderConfigurationError,
    ProviderNotImplementedError,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.common import ErrorResponse
from app.schemas.embedding import EmbeddingRequest, EmbeddingResponse
from app.services.embedding_service import embed_texts

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

_EMBEDDING_GENERATE_EXAMPLES = {
    "ollama": {
        "summary": "Generate embeddings with Ollama",
        "value": {
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "input_texts": ["Invoice #001. Total due is $150."],
        },
    }
}


@router.post(
    "/generate",
    response_model=EmbeddingResponse,
    summary="Generate embeddings",
    description="Produce vector embeddings for the supplied texts using the selected provider.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request or provider configuration."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        501: {"model": ErrorResponse, "description": "Provider capability not implemented."},
        502: {"model": ErrorResponse, "description": "Embedding provider upstream failure."},
    },
)
async def generate_embeddings(
    payload: Annotated[EmbeddingRequest, Body(openapi_examples=_EMBEDDING_GENERATE_EXAMPLES)],
) -> EmbeddingResponse:
    try:
        result = await embed_texts(
            provider=payload.provider,
            model_name=payload.model_name,
            input_texts=payload.input_texts,
            api_key=payload.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderNotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ProviderUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return EmbeddingResponse(**result)
