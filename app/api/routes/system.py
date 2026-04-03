import sys
from typing import Final

from fastapi import APIRouter

from app.core.settings import settings
from app.schemas.common import HealthResponse, InfoResponse

router = APIRouter(tags=["system"])

SUPPORTED_PROVIDERS: Final[list[str]] = [
    "ollama",
    "openai",
    "gemini",
    "anthropic",
]

SUPPORTED_OCR_ENGINES: Final[list[str]] = [
    "deepseek-ocr",
    "glm-ocr",
]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Legacy health check",
    description="Return a simple health status. Prefer /health/live and /health/ready.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/info",
    response_model=InfoResponse,
    summary="Application info",
    description="Return application metadata and supported provider/engine lists.",
)
def info() -> InfoResponse:
    return InfoResponse(
        app_name=settings.app_name,
        version=settings.version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        supported_providers=SUPPORTED_PROVIDERS,
        supported_ocr_engines=SUPPORTED_OCR_ENGINES,
    )
