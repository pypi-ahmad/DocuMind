"""Job queue facade — delegates to in-memory or Redis backend based on config."""

import asyncio
import uuid
from typing import Any

from app.core.settings import settings
from app.schemas.jobs import JobResponse, JobStatus

# --- In-memory backend (default) ---

_jobs: dict[str, JobResponse] = {}
_job_secrets: dict[str, dict[str, Any]] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()


def _memory_create_job(job_type: str, input_data: dict[str, Any]) -> JobResponse:
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


def _memory_get_job(job_id: str) -> JobResponse | None:
    return _jobs.get(job_id)


def _memory_get_all_jobs() -> list[JobResponse]:
    return list(_jobs.values())


def _memory_get_job_input(job_id: str) -> dict[str, Any] | None:
    job = _jobs.get(job_id)
    if job is None:
        return None

    secret_values = _job_secrets.get(job_id, {})
    return {
        **job.input,
        **secret_values,
    }


def _memory_update_job(
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


async def _memory_enqueue_job(job_id: str) -> None:
    await _queue.put(job_id)


async def _memory_dequeue_job() -> str:
    return await _queue.get()


def _memory_clear_job_secrets(job_id: str) -> None:
    _job_secrets.pop(job_id, None)


# --- Dispatch ---

def _use_redis() -> bool:
    return settings.job_queue_backend.strip().lower() == "redis"


def create_job(job_type: str, input_data: dict[str, Any]) -> JobResponse:
    if _use_redis():
        from app.workers.redis_queue import create_job as _redis_create
        return _redis_create(job_type, input_data)
    return _memory_create_job(job_type, input_data)


def get_job(job_id: str) -> JobResponse | None:
    if _use_redis():
        from app.workers.redis_queue import get_job as _redis_get
        return _redis_get(job_id)
    return _memory_get_job(job_id)


def get_all_jobs() -> list[JobResponse]:
    if _use_redis():
        from app.workers.redis_queue import get_all_jobs as _redis_all
        return _redis_all()
    return _memory_get_all_jobs()


def get_job_input(job_id: str) -> dict[str, Any] | None:
    if _use_redis():
        from app.workers.redis_queue import get_job_input as _redis_input
        return _redis_input(job_id)
    return _memory_get_job_input(job_id)


def update_job(
    job_id: str,
    *,
    status: JobStatus | None = None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    if _use_redis():
        from app.workers.redis_queue import update_job as _redis_update
        _redis_update(job_id, status=status, result=result, error=error)
        return
    _memory_update_job(job_id, status=status, result=result, error=error)


async def enqueue_job(job_id: str) -> None:
    if _use_redis():
        from app.workers.redis_queue import enqueue_job as _redis_enqueue
        await _redis_enqueue(job_id)
        return
    await _memory_enqueue_job(job_id)


async def dequeue_job() -> str:
    if _use_redis():
        from app.workers.redis_queue import dequeue_job as _redis_dequeue
        return await _redis_dequeue()
    return await _memory_dequeue_job()


def clear_job_secrets(job_id: str) -> None:
    if _use_redis():
        from app.workers.redis_queue import clear_job_secrets as _redis_clear
        _redis_clear(job_id)
        return
    _memory_clear_job_secrets(job_id)
