from pydantic import BaseModel


class RuntimeStatusResponse(BaseModel):
    active_provider: str | None = None
    active_model: str | None = None
    busy: bool
    loaded_at: str | None = None


class ActivateModelRequest(BaseModel):
    provider: str
    model_name: str


class ActivateModelResponse(BaseModel):
    active_provider: str | None = None
    active_model: str | None = None
    busy: bool
    loaded_at: str | None = None
    message: str


class DeactivateModelResponse(BaseModel):
    success: bool
    message: str