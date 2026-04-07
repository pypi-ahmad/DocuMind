"""Centralized exception handlers for consistent error responses."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_FIELD_LABELS: dict[str, str] = {
    "model_name": "Model",
    "provider": "Provider",
    "file_path": "Document file",
    "doc_id": "Document ID",
    "query": "Question",
    "ocr_result": "OCR result",
    "engine": "OCR engine",
    "ocr_engine": "OCR engine",
    "api_key": "API key",
    "embedding_provider": "Search provider",
    "embedding_model_name": "Search model",
    "pipeline_name": "Pipeline",
    "input": "Input",
    "retrieval_mode": "Retrieval mode",
    "top_k": "Number of results",
    "rerank_top_k": "Re-rank results",
    "temperature": "Temperature",
    "max_output_tokens": "Max output length",
    "prefer_structure": "Structured output",
    "metadata": "Metadata",
}


def _friendly_loc(loc: list) -> str:
    """Convert a Pydantic error location tuple to a human-readable field label."""
    parts = [p for p in loc if p not in ("body", "query", "path") and not isinstance(p, int)]
    if not parts:
        return "Input"
    last = str(parts[-1])
    return _FIELD_LABELS.get(last, last.replace("_", " ").capitalize())


def _friendly_msg(msg: str) -> str:
    """Simplify Pydantic message text."""
    lower = msg.lower()
    if "field required" in lower:
        return "is required"
    if "value error" in lower:
        return msg.split(",", 1)[-1].strip().capitalize() if "," in msg else msg
    return msg


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail if isinstance(exc.detail, str) else "HTTP error",
            "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "request_id": request_id,
        },
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = _get_request_id(request)
    errors = exc.errors()
    messages = [
        f"{_friendly_loc(list(e.get('loc', [])))}: {_friendly_msg(e.get('msg', ''))}"
        for e in errors
    ]
    summary = "; ".join(messages)
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": summary,
            "request_id": request_id,
        },
    )


async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _get_request_id(request)
    logger.exception("Unhandled exception [request_id=%s]", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred.",
            "request_id": request_id,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _generic_exception_handler)
