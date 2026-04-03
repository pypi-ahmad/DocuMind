import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.eval import router as eval_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.llm import router as llm_router
from app.api.routes.ocr import router as ocr_router
from app.api.routes.embeddings import router as embeddings_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.pipelines import router as pipelines_router
from app.api.routes.providers import router as providers_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.ui import router as ui_router
from app.api.router import api_router
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware, RequestTimingMiddleware
from app.core.model_manager import model_manager
from app.core.settings import settings
from app.schemas.common import LivenessResponse, ReadinessResponse
from app.workers.queue import _queue
from app.workers.worker import start_worker, stop_worker

configure_logging()

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {"name": "health", "description": "Operational liveness and readiness probes."},
    {"name": "providers", "description": "Provider discovery and model listing endpoints."},
    {"name": "runtime", "description": "Runtime model activation and current state endpoints."},
    {"name": "jobs", "description": "Background job submission and polling endpoints."},
    {"name": "ocr", "description": "OCR routing, extraction, and post-processing endpoints."},
    {"name": "llm", "description": "Text generation endpoints across supported providers."},
    {"name": "retrieval", "description": "Indexing, search, reranking, and document QA endpoints."},
    {"name": "pipelines", "description": "Pipeline discovery and execution endpoints."},
    {"name": "evaluation", "description": "Benchmark and stress testing endpoints."},
    {"name": "ui", "description": "Frontend-facing capability and configuration endpoints."},
    {"name": "embeddings", "description": "Vector embedding generation endpoints."},
    {"name": "system", "description": "Legacy system health and info endpoints."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s", settings.app_name, settings.version)
    start_worker()
    yield
    await stop_worker()
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title="DocuMind API",
    version=settings.version,
    description=(
        "DocuMind is an OCR-first API platform for extracting, structuring, indexing, "
        "evaluating, and querying document content across pluggable providers."
    ),
    contact={
        "name": "DocuMind API Support",
        "url": "https://example.com/support",
    },
    license_info={
        "name": "License Placeholder",
        "url": "https://example.com/license",
    },
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# -- Middleware (outermost first) --
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)

cors_allow_origins = settings.cors_allow_origins
if isinstance(cors_allow_origins, str):
    cors_allow_origins = [cors_allow_origins]

if cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# -- Exception handlers --
register_exception_handlers(app)

# -- Routers --
app.include_router(api_router)
app.include_router(providers_router)
app.include_router(llm_router)
app.include_router(embeddings_router)
app.include_router(retrieval_router)
app.include_router(pipelines_router)
app.include_router(jobs_router)
app.include_router(runtime_router)
app.include_router(ocr_router)
app.include_router(eval_router)
app.include_router(ui_router)


# -- Health probes --


@app.get(
    "/health/live",
    response_model=LivenessResponse,
    tags=["health"],
    summary="Liveness probe",
    description="Return a simple liveness status to confirm the API process is running.",
)
def health_live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    tags=["health"],
    summary="Readiness probe",
    description="Return a lightweight readiness view for the in-memory queue and model manager.",
)
def health_ready() -> ReadinessResponse:
    queue_ok = _queue is not None
    model_manager_ok = model_manager is not None
    all_ok = queue_ok and model_manager_ok

    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        checks={
            "queue_initialized": queue_ok,
            "model_manager_accessible": model_manager_ok,
        },
    )
