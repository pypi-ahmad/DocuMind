from dataclasses import dataclass
from typing import Final, Literal


PipelineStepKind = Literal["ocr_extract", "ocr_postprocess"]


@dataclass(frozen=True, slots=True)
class PipelineStepDefinition:
    name: str
    kind: PipelineStepKind
    description: str
    task: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineDefinition:
    name: str
    description: str
    steps: tuple[PipelineStepDefinition, ...]
    required_input_fields: tuple[str, ...]
    optional_input_fields: tuple[str, ...] = ()


PIPELINE_DEFINITIONS: Final[dict[str, PipelineDefinition]] = {
    "ocr_extract_only": PipelineDefinition(
        name="ocr_extract_only",
        description="Run OCR extraction and return the normalized structured OCR output.",
        steps=(
            PipelineStepDefinition(
                name="ocr_extract",
                kind="ocr_extract",
                description="Extract OCR text and return normalized structured output.",
            ),
        ),
        required_input_fields=("file_path",),
        optional_input_fields=("engine", "prefer_structure"),
    ),
    "ocr_extract_then_summary": PipelineDefinition(
        name="ocr_extract_then_summary",
        description="Run OCR extraction and summarize the OCR result with the selected LLM provider.",
        steps=(
            PipelineStepDefinition(
                name="ocr_extract",
                kind="ocr_extract",
                description="Extract OCR text and return normalized structured output.",
            ),
            PipelineStepDefinition(
                name="ocr_postprocess_summary",
                kind="ocr_postprocess",
                description="Summarize the OCR result using the pluggable LLM layer.",
                task="summary",
            ),
        ),
        required_input_fields=("file_path", "provider", "model_name"),
        optional_input_fields=(
            "engine",
            "prefer_structure",
            "api_key",
            "temperature",
            "max_output_tokens",
        ),
    ),
    "ocr_extract_then_key_fields": PipelineDefinition(
        name="ocr_extract_then_key_fields",
        description="Run OCR extraction and extract key fields from the OCR result with the selected LLM provider.",
        steps=(
            PipelineStepDefinition(
                name="ocr_extract",
                kind="ocr_extract",
                description="Extract OCR text and return normalized structured output.",
            ),
            PipelineStepDefinition(
                name="ocr_postprocess_key_fields",
                kind="ocr_postprocess",
                description="Extract key fields from the OCR result using the pluggable LLM layer.",
                task="extract_key_fields",
            ),
        ),
        required_input_fields=("file_path", "provider", "model_name"),
        optional_input_fields=(
            "engine",
            "prefer_structure",
            "api_key",
            "temperature",
            "max_output_tokens",
        ),
    ),
}