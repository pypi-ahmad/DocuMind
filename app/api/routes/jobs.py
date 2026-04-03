from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, status

from app.schemas.common import ErrorResponse
from app.schemas.jobs import CreateJobRequest, JobResponse
from app.workers.queue import create_job, enqueue_job, get_all_jobs, get_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

_CREATE_JOB_EXAMPLES = {
    "retrieval_qa": {
        "summary": "Queue a document QA job",
        "value": {
            "type": "retrieval.qa",
            "input": {
                "query": "When does the contract start?",
                "provider": "ollama",
                "model_name": "llama3",
                "retrieval_mode": "hybrid",
                "top_k": 3,
                "use_rerank": True,
                "rerank_top_k": 2,
            },
        },
    }
}


def _normalize_job_input(job_type: str, input_data: dict[str, Any]) -> dict[str, Any]:
    normalized_input = dict(input_data)

    if job_type != "pipeline.run":
        return normalized_input

    pipeline_input = normalized_input.get("input")
    if not isinstance(pipeline_input, dict):
        return normalized_input

    pipeline_input_copy = dict(pipeline_input)
    api_key = pipeline_input_copy.pop("api_key", None)
    normalized_input["input"] = pipeline_input_copy

    if api_key is not None:
        normalized_input["api_key"] = api_key

    return normalized_input


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a job",
    description="Create a background job and enqueue it for processing.",
)
async def submit_job(
    payload: Annotated[CreateJobRequest, Body(openapi_examples=_CREATE_JOB_EXAMPLES)],
) -> JobResponse:
    job = create_job(payload.type, _normalize_job_input(payload.type, payload.input))
    await enqueue_job(job.job_id)
    return job


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Fetch the current state, result, and error information for a queued job.",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found."},
    },
)
def retrieve_job(job_id: str) -> JobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get(
    "",
    response_model=list[JobResponse],
    summary="List jobs",
    description="Return all jobs currently tracked in the in-memory queue.",
)
def list_jobs() -> list[JobResponse]:
    return get_all_jobs()
