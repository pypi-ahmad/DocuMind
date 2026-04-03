from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, status

from app.schemas.common import ErrorResponse
from app.schemas.pipeline import PipelineSummary, RunPipelineRequest, RunPipelineResponse
from app.services.pipeline_runner import PipelineNotFoundError, list_pipelines, run_pipeline

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

_RUN_PIPELINE_EXAMPLES = {
    "ocr_index": {
        "summary": "Run a pipeline with OCR-style input",
        "value": {
            "pipeline_name": "ocr_extract_only",
            "input": {
                "file_path": "sample-docs/invoice.png",
                "prefer_structure": True,
            },
        },
    }
}


@router.get(
    "",
    response_model=list[PipelineSummary],
    summary="List pipelines",
    description="Return the available pipeline definitions and their descriptions.",
)
def get_pipelines() -> list[PipelineSummary]:
    return [PipelineSummary(**pipeline) for pipeline in list_pipelines()]


@router.post(
    "/run",
    response_model=RunPipelineResponse,
    summary="Run a pipeline",
    description="Execute a named pipeline with the provided input payload.",
    responses={
        404: {"model": ErrorResponse, "description": "Pipeline not found."},
    },
)
async def execute_pipeline(
    payload: Annotated[RunPipelineRequest, Body(openapi_examples=_RUN_PIPELINE_EXAMPLES)],
) -> RunPipelineResponse:
    try:
        result = await run_pipeline(payload.pipeline_name, payload.input)
    except PipelineNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return RunPipelineResponse(**result)