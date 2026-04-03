from pydantic import BaseModel


class ModelOption(BaseModel):
    id: str
    display_name: str
    provider: str


class ProviderModelsRequest(BaseModel):
    api_key: str | None = None


class ProviderModelsResponse(BaseModel):
    provider: str
    models: list[ModelOption]


class ProviderDescriptor(BaseModel):
    provider: str
    requires_api_key: bool
    supports_byok: bool = False
    has_env_key: bool = False