import asyncio
import uuid
from typing import Any

from app.schemas.jobs import JobResponse, JobStatus


_jobs: dict[str, JobResponse] = {}
_job_secrets: dict[str, dict[str, Any]] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()


def create_job(job_type: str, input_data: dict[str, Any]) -> JobResponse:
    job_id = uuid.uuid4().hex
    stored_input = dict(input_data)
    secret_values: dict[str, Any] = {}

    api_key = stored_input.pop("api_key", None)
    if api_key is not None:
        secret_values["api_key"] = api_key

    job = JobResponse(
        job_id=job_id,
        type=job_type,
        status=JobStatus.PENDING,
        input=stored_input,
    )
    _jobs[job_id] = job
    if secret_values:
        _job_secrets[job_id] = secret_values
    return job


def get_job(job_id: str) -> JobResponse | None:
    return _jobs.get(job_id)


def get_all_jobs() -> list[JobResponse]:
    return list(_jobs.values())


def get_job_input(job_id: str) -> dict[str, Any] | None:
    job = _jobs.get(job_id)
    if job is None:
        return None

    secret_values = _job_secrets.get(job_id, {})
    return {
        **job.input,
        **secret_values,
    }


def update_job(
    job_id: str,
    *,
    status: JobStatus | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return

    if status is not None:
        job.status = status
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error


async def enqueue_job(job_id: str) -> None:
    await _queue.put(job_id)


async def dequeue_job() -> str:
    return await _queue.get()


def clear_job_secrets(job_id: str) -> None:
    _job_secrets.pop(job_id, None)
