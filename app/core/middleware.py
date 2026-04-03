"""Request-level middleware for tracing and timing."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.settings import settings

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if settings.enable_request_id:
            request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        else:
            request_id = None

        request.state.request_id = request_id
        response = await call_next(request)

        if request_id is not None:
            response.headers["X-Request-ID"] = request_id

        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Process-Time-MS"] = str(elapsed_ms)

        request_id = getattr(request.state, "request_id", None)
        logger.info(
            "%s %s -> %s (%.2fms) [request_id=%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id or "-",
        )

        return response
