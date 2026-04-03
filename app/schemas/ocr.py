from typing import Any, Literal

from pydantic import BaseModel, Field


POSTPROCESS_TASKS = {"cleanup", "summary", "extract_key_fields"}

PostProcessTask = Literal["cleanup", "summary", "extract_key_fields"]


class OCRExtractRequest(BaseModel):
    file_path: str
    engine: str | None = None
    prefer_structure: bool = False


class OCRNormalizationSummary(BaseModel):
    removed_blank_lines: int
    collapsed_whitespace: bool
    merged_broken_lines: bool
    cleaned_hyphenation: bool


class OCRPageResult(BaseModel):
    page: int
    text: str
    confidence: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRExtractResponse(BaseModel):
    engine: str
    text: str
    normalized_text: str
    normalization: OCRNormalizationSummary
    structured: dict
    layout: dict
    tables: list[dict]
    confidence: float
    metadata: dict
    pages: list[OCRPageResult] = Field(default_factory=list)


class OCRRouteDecisionResponse(BaseModel):
    selected_engine: str
    reason: str


class OCRPostProcessRequest(BaseModel):
    ocr_result: dict[str, Any]
    task: PostProcessTask
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0)
    max_output_tokens: int | None = Field(default=None, gt=0)


class OCRPostProcessResponse(BaseModel):
    task: str
    provider: str
    model_name: str
    output_text: str
    usage: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
