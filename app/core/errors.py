"""Centralized exception handlers for consistent error responses."""

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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
    summary = "; ".join(
        f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}"
        for e in errors
    )
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
