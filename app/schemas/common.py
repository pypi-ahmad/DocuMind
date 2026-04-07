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
