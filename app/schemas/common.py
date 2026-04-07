from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str


class InfoResponse(BaseModel):
    app_name: str
    version: str
    python_version: str
    supported_providers: list[str]
    supported_ocr_engines: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Validation error",
                "detail": "body.model_name: Field required",
                "request_id": "5a95bf37d3f14a74b9bced2d2fb803b8",
            }
        }
    )


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


class UIConfigBYOKResponse(BaseModel):
    openai: bool
    gemini: bool
    anthropic: bool


class UIConfigResponse(BaseModel):
    app_name: str
    version: str
    supported_providers: list[str]
    supported_ocr_engines: list[str]
    supported_retrieval_modes: list[str]
    supported_postprocess_tasks: list[str]
    supports_byok: UIConfigBYOKResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "DocuMind",
                "version": "0.1.0",
                "supported_providers": ["ollama", "openai", "gemini", "anthropic"],
                "supported_ocr_engines": ["deepseek-ocr", "glm-ocr"],
                "supported_retrieval_modes": ["dense", "hybrid"],
                "supported_postprocess_tasks": ["cleanup", "summary", "extract_key_fields"],
                "supports_byok": {
                    "openai": True,
                    "gemini": True,
                    "anthropic": True,
                },
            }
        }
    )
