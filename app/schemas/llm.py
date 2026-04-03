from typing import Any

from pydantic import BaseModel, Field


class LLMGenerateRequest(BaseModel):
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, gt=0)


class LLMUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMGenerateResponse(BaseModel):
    provider: str
    model_name: str
    text: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    metadata: dict[str, Any] = Field(default_factory=dict)