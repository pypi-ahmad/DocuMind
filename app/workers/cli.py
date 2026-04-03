"""Standalone worker process for multi-node deployments.

When using Redis as the job queue backend, run one or more worker instances
separately from the API process:

    python -m app.workers.cli

Each worker pops jobs from the shared Redis queue, executes them, and writes
results back.  This allows horizontal scaling of job execution independently
from the API tier.

Requirements:
    - DOCUMIND_JOB_QUEUE_BACKEND=redis
    - DOCUMIND_REDIS_URL=redis://...
    - If using Milvus: DOCUMIND_VECTOR_STORE_BACKEND=milvus
"""

import asyncio
import logging

from app.core.logging import configure_logging
from app.core.settings import settings

configure_logging()

logger = logging.getLogger(__name__)


async def _run_standalone_worker() -> None:
    from app.workers.queue import dequeue_job
    from app.workers.worker import _process_job

    logger.info(
        "Standalone worker started (queue=%s, store=%s)",
        settings.job_queue_backend,
        settings.vector_store_backend,
    )

    while True:
        job_id = await dequeue_job()
        logger.info("Worker picked up job %s", job_id)
        await _process_job(job_id)


def main() -> None:
    if settings.job_queue_backend.strip().lower() != "redis":
        logger.error(
            "Standalone worker requires DOCUMIND_JOB_QUEUE_BACKEND=redis "
            "(current: %s)",
            settings.job_queue_backend,
        )
        raise SystemExit(1)

    try:
        asyncio.run(_run_standalone_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down")


if __name__ == "__main__":
    main()
