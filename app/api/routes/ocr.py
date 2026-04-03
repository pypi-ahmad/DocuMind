from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.core.model_manager import model_manager
from app.ocr.normalize import normalize_ocr_result
from app.ocr.structure import structure_ocr_result
from app.ocr.router import VALID_ENGINES, get_engine, select_engine
from app.providers.base import (
    ProviderConfigurationError,
    ProviderUnauthorizedError,
    ProviderUpstreamError,
)
from app.schemas.common import ErrorResponse
from app.schemas.ocr import (
    OCRExtractRequest,
    OCRExtractResponse,
    OCRPostProcessRequest,
    OCRPostProcessResponse,
    OCRRouteDecisionResponse,
)
from app.services.ocr_postprocess import run_ocr_postprocess

router = APIRouter(prefix="/ocr", tags=["ocr"])

_OCR_EXTRACT_EXAMPLES = {
    "default": {
        "summary": "Extract OCR text from an invoice image",
        "value": {
            "file_path": "sample-docs/invoice.png",
            "prefer_structure": True,
        },
    }
}

_OCR_POSTPROCESS_EXAMPLES = {
    "summary": {
        "summary": "Summarize OCR output",
        "value": {
            "ocr_result": {
                "text": "Invoice #123 for ACME Corp. Total due is $150.",
                "normalized_text": "Invoice #123 for ACME Corp. Total due is $150.",
            },
            "task": "summary",
            "provider": "ollama",
            "model_name": "llama3",
            "temperature": 0,
        },
    }
}


@router.post(
    "/route",
    response_model=OCRRouteDecisionResponse,
    summary="Route OCR request",
    description="Choose the OCR engine that best fits the requested file and structure preference.",
)
def route_ocr(
    payload: Annotated[OCRExtractRequest, Body(openapi_examples=_OCR_EXTRACT_EXAMPLES)],
) -> OCRRouteDecisionResponse:
    decision = select_engine(payload.file_path, payload.prefer_structure)
    return OCRRouteDecisionResponse(**decision)


@router.post(
    "/extract",
    response_model=OCRExtractResponse,
    summary="Extract OCR content",
    description="Run OCR extraction and normalization on the requested document.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid OCR request or file path."},
        502: {"model": ErrorResponse, "description": "OCR engine upstream failure."},
    },
)
async def extract_ocr(
    payload: Annotated[OCRExtractRequest, Body(openapi_examples=_OCR_EXTRACT_EXAMPLES)],
) -> OCRExtractResponse:
    if payload.engine is not None:
        if payload.engine not in VALID_ENGINES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid engine '{payload.engine}'. Must be one of: {', '.join(sorted(VALID_ENGINES))}",
            )
        engine_name = payload.engine
    else:
        decision = select_engine(payload.file_path, payload.prefer_structure)
        engine_name = decision["selected_engine"]

    engine = get_engine(engine_name)
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Engine '{engine_name}' is not available",
        )

    await model_manager.activate("ollama", engine.model_name)
    model_manager.mark_busy()
    try:
        result = await engine.extract(payload.file_path)
        result = normalize_ocr_result(result)
        result = structure_ocr_result(result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (TimeoutError, ConnectionError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    finally:
        model_manager.mark_idle()

    return OCRExtractResponse(**result)


@router.post(
    "/postprocess",
    response_model=OCRPostProcessResponse,
    summary="Post-process OCR output",
    description="Use an LLM provider to clean up, summarize, or extract structured fields from OCR output.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid OCR post-process request."},
        401: {"model": ErrorResponse, "description": "Provider authentication failed."},
        502: {"model": ErrorResponse, "description": "Provider upstream failure."},
    },
)
async def postprocess_ocr(
    payload: Annotated[OCRPostProcessRequest, Body(openapi_examples=_OCR_POSTPROCESS_EXAMPLES)],
) -> OCRPostProcessResponse:
    try:
        result = await run_ocr_postprocess(
            ocr_result=payload.ocr_result,
            task=payload.task,
            provider=payload.provider,
            model_name=payload.model_name,
            api_key=payload.api_key,
            temperature=payload.temperature,
            max_output_tokens=payload.max_output_tokens,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProviderUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ProviderUpstreamError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return OCRPostProcessResponse(**result)
