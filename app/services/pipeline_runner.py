from typing import Any

from app.core.model_manager import model_manager
from app.core.pipelines import PIPELINE_DEFINITIONS, PipelineDefinition, PipelineStepDefinition
from app.ocr.normalize import normalize_ocr_result
from app.ocr.router import resolve_engine
from app.ocr.structure import structure_ocr_result
from app.services.ocr_postprocess import run_ocr_postprocess


class PipelineNotFoundError(Exception):
    pass


def list_pipelines() -> list[dict[str, str]]:
    return [
        {
            "pipeline_name": definition.name,
            "description": definition.description,
        }
        for definition in PIPELINE_DEFINITIONS.values()
    ]


def _get_pipeline_definition(pipeline_name: str) -> PipelineDefinition:
    normalized_name = pipeline_name.strip()
    pipeline = PIPELINE_DEFINITIONS.get(normalized_name)
    if pipeline is None:
        raise PipelineNotFoundError(f"Pipeline '{normalized_name}' not found")
    return pipeline


def _require_non_empty_str(input_data: dict[str, Any], key: str, *, context: str) -> str:
    value = input_data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires a non-empty {key}")
    return value.strip()


async def _run_ocr_extract_step(input_data: dict[str, Any]) -> dict[str, Any]:
    file_path = _require_non_empty_str(input_data, "file_path", context="ocr_extract step")

    engine_value = input_data.get("engine")
    if engine_value is not None and not isinstance(engine_value, str):
        raise ValueError("ocr_extract step engine must be a string when provided")

    prefer_structure = input_data.get("prefer_structure", False)
    if not isinstance(prefer_structure, bool):
        raise ValueError("ocr_extract step prefer_structure must be a boolean")

    engine = resolve_engine(engine_value, file_path, prefer_structure)

    await model_manager.activate("ollama", engine.model_name)
    model_manager.mark_busy()
    try:
        result = await engine.extract(file_path)
        result = normalize_ocr_result(result)
        return structure_ocr_result(result)
    finally:
        model_manager.mark_idle()


async def _run_ocr_postprocess_step(
    input_data: dict[str, Any],
    *,
    ocr_result: dict[str, Any],
    task: str,
) -> dict[str, Any]:
    provider = _require_non_empty_str(input_data, "provider", context="ocr_postprocess step")
    model_name = _require_non_empty_str(input_data, "model_name", context="ocr_postprocess step")

    api_key = input_data.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError("ocr_postprocess step api_key must be a string when provided")

    temperature = input_data.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, (int, float)) or temperature < 0:
            raise ValueError("ocr_postprocess step temperature must be a non-negative number")
        temperature = float(temperature)

    max_output_tokens = input_data.get("max_output_tokens")
    if max_output_tokens is not None:
        if not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            raise ValueError("ocr_postprocess step max_output_tokens must be a positive integer")

    return await run_ocr_postprocess(
        ocr_result=ocr_result,
        task=task,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


async def _execute_step(
    step: PipelineStepDefinition,
    input_data: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    if step.kind == "ocr_extract":
        return await _run_ocr_extract_step(input_data)

    if step.kind == "ocr_postprocess":
        ocr_result = context.get("ocr_result")
        if not isinstance(ocr_result, dict):
            raise ValueError("ocr_postprocess step requires OCR output from a previous step")
        if step.task is None:
            raise ValueError(f"Pipeline step '{step.name}' is missing a task")
        return await _run_ocr_postprocess_step(input_data, ocr_result=ocr_result, task=step.task)

    raise ValueError(f"Unsupported pipeline step kind: {step.kind}")


async def run_pipeline(pipeline_name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    pipeline = _get_pipeline_definition(pipeline_name)

    if not isinstance(input_data, dict):
        raise ValueError("Pipeline input must be an object")

    step_results: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    final_output: dict[str, Any] | None = None
    status = "completed"

    for step in pipeline.steps:
        try:
            output = await _execute_step(step, input_data, context)
            step_results.append(
                {
                    "step_name": step.name,
                    "status": "completed",
                    "output": output,
                    "error": None,
                }
            )
            if step.kind == "ocr_extract":
                context["ocr_result"] = output
            final_output = output
        except Exception as exc:
            step_results.append(
                {
                    "step_name": step.name,
                    "status": "failed",
                    "output": None,
                    "error": str(exc),
                }
            )
            status = "failed"
            break

    return {
        "pipeline_name": pipeline.name,
        "status": status,
        "steps": step_results,
        "final_output": final_output,
    }