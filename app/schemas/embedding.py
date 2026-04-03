from typing import Any

from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    input_texts: list[str] = Field(min_length=1)
    api_key: str | None = None


class EmbeddingVector(BaseModel):
    index: int
    vector: list[float]


class EmbeddingResponse(BaseModel):
    provider: str
    model_name: str
    vectors: list[EmbeddingVector]
    metadata: dict[str, Any] = Field(default_factory=dict)
