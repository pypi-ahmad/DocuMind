"""Redis-backed job queue implementing the same interface as the in-memory queue."""

import json
import uuid
from typing import Any

import redis

from app.core.settings import settings
from app.schemas.jobs import JobResponse, JobStatus

_redis_client: redis.Redis | None = None

_JOBS_HASH = "documind:jobs"
_SECRETS_HASH = "documind:job_secrets"
_QUEUE_KEY = "documind:job_queue"


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def create_job(job_type: str, input_data: dict[str, Any]) -> JobResponse:
    r = _get_redis()
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
    r.hset(_JOBS_HASH, job_id, job.model_dump_json())
    if secret_values:
        r.hset(_SECRETS_HASH, job_id, json.dumps(secret_values))
    return job


def get_job(job_id: str) -> JobResponse | None:
    r = _get_redis()
    data = r.hget(_JOBS_HASH, job_id)
    if data is None:
        return None
    return JobResponse.model_validate_json(data)


def get_all_jobs() -> list[JobResponse]:
    r = _get_redis()
    all_data = r.hvals(_JOBS_HASH)
    return [JobResponse.model_validate_json(d) for d in all_data]


def get_job_input(job_id: str) -> dict[str, Any] | None:
    job = get_job(job_id)
    if job is None:
        return None

    r = _get_redis()
    secret_raw = r.hget(_SECRETS_HASH, job_id)
    secret_values = json.loads(secret_raw) if secret_raw else {}
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
    job = get_job(job_id)
    if job is None:
        return

    if status is not None:
        job.status = status
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error

    r = _get_redis()
    r.hset(_JOBS_HASH, job_id, job.model_dump_json())


async def enqueue_job(job_id: str) -> None:
    r = _get_redis()
    r.rpush(_QUEUE_KEY, job_id)


async def dequeue_job() -> str:
    """Blocking pop from Redis queue.  Runs in a thread to avoid blocking the event loop."""
    import asyncio
    loop = asyncio.get_running_loop()

    def _blocking_pop() -> str:
        r = _get_redis()
        # BLPOP blocks until an item is available (timeout=0 means wait forever)
        _, job_id = r.blpop(_QUEUE_KEY, timeout=0)  # type: ignore[misc]
        return str(job_id)

    return await loop.run_in_executor(None, _blocking_pop)


def clear_job_secrets(job_id: str) -> None:
    r = _get_redis()
    r.hdel(_SECRETS_HASH, job_id)
