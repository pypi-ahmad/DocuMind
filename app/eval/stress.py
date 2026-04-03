import asyncio
import math
import time
from typing import Any, Awaitable, Callable

from app.schemas.eval import StressMetric
from app.services.document_qa import answer_document_query
from app.services.embedding_service import search_similar
from app.services.hybrid_retrieval import hybrid_search
from app.workers.queue import create_job, enqueue_job

ALLOWED_STRESS_TEST_TYPES = frozenset({"job_submit", "retrieval_search", "document_qa"})
_MAX_FAILURE_SUMMARIES = 10


def _safe_average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _p95_latency(values: list[float]) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    rank = max(1, math.ceil(0.95 * len(ordered)))
    return ordered[rank - 1]


async def _run_concurrent_requests(
    *,
    test_type: str,
    concurrency: int,
    iterations: int,
    request_factory: Callable[[], Awaitable[dict[str, Any]]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_requests = concurrency * iterations
    semaphore = asyncio.Semaphore(concurrency)
    started_at = time.perf_counter()

    async def _invoke(request_index: int) -> dict[str, Any]:
        async with semaphore:
            request_started_at = time.perf_counter()
            try:
                await request_factory()
                success = True
                error = None
            except Exception as exc:
                success = False
                error = str(exc)[:200]

            latency_ms = round((time.perf_counter() - request_started_at) * 1000, 2)
            return {
                "request_index": request_index,
                "success": success,
                "latency_ms": latency_ms,
                "error": error,
            }

    tasks = [asyncio.create_task(_invoke(index + 1)) for index in range(total_requests)]
    results = await asyncio.gather(*tasks)

    latencies = [float(result["latency_ms"]) for result in results]
    successful_requests = sum(1 for result in results if result["success"])
    failed_requests = total_requests - successful_requests
    failures = [
        {
            "request_index": result["request_index"],
            "latency_ms": result["latency_ms"],
            "error": result["error"],
        }
        for result in results
        if not result["success"]
    ][:_MAX_FAILURE_SUMMARIES]

    total_elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    throughput_rps = 0.0
    if total_elapsed_ms > 0:
        throughput_rps = round(total_requests / (total_elapsed_ms / 1000), 3)

    average_latency_ms = round(_safe_average(latencies), 2)
    p95_latency_ms = round(_p95_latency(latencies), 2)

    return {
        "test_type": test_type,
        "concurrency": concurrency,
        "iterations": iterations,
        "total_requests": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "average_latency_ms": average_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "metrics": [
            StressMetric(
                name="success_rate",
                value=round(successful_requests / total_requests, 4) if total_requests else 0.0,
            ).model_dump(),
            StressMetric(name="throughput_rps", value=throughput_rps).model_dump(),
        ],
        "failures": failures,
        "metadata": {
            "p95_method": "nearest-rank",
            "failure_sample_limit": _MAX_FAILURE_SUMMARIES,
            "total_elapsed_ms": total_elapsed_ms,
            **(metadata or {}),
        },
    }


async def run_job_submit_stress(
    *,
    concurrency: int,
    iterations: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    job_type = payload.get("type")
    job_input = payload.get("input")

    async def _submit_job() -> dict[str, Any]:
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("payload.type must be a non-empty string")
        if not isinstance(job_input, dict):
            raise ValueError("payload.input must be a dict")

        job = create_job(job_type.strip(), dict(job_input))
        await enqueue_job(job.job_id)

        if not job.job_id or not job.status:
            raise ValueError("job submission returned an invalid job response")

        return {"job_id": job.job_id, "status": job.status}

    return await _run_concurrent_requests(
        test_type="job_submit",
        concurrency=concurrency,
        iterations=iterations,
        request_factory=_submit_job,
        metadata={"job_type": job_type if isinstance(job_type, str) else ""},
    )


async def run_retrieval_search_stress(
    *,
    concurrency: int,
    iterations: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    mode_value = payload.get("retrieval_mode", payload.get("mode", "dense"))

    async def _run_search() -> dict[str, Any]:
        if not isinstance(payload.get("query"), str) or not payload["query"].strip():
            raise ValueError("payload.query must be a non-empty string")
        if not isinstance(payload.get("provider"), str) or not payload["provider"].strip():
            raise ValueError("payload.provider must be a non-empty string")
        if not isinstance(payload.get("model_name"), str) or not payload["model_name"].strip():
            raise ValueError("payload.model_name must be a non-empty string")

        top_k = payload.get("top_k", 5)
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("payload.top_k must be a positive integer")

        mode = mode_value.strip().lower() if isinstance(mode_value, str) else "dense"
        if mode == "hybrid":
            result = await hybrid_search(
                payload["query"],
                payload["provider"],
                payload["model_name"],
                api_key=payload.get("api_key"),
                top_k=top_k,
                dense_weight=float(payload.get("dense_weight", 0.5)),
                sparse_weight=float(payload.get("sparse_weight", 0.5)),
            )
            if not isinstance(result, dict) or "hits" not in result:
                raise ValueError("hybrid retrieval returned an invalid response")
            return result

        if mode != "dense":
            raise ValueError("payload.retrieval_mode must be one of: dense, hybrid")

        result = await search_similar(
            query=payload["query"],
            provider=payload["provider"],
            model_name=payload["model_name"],
            api_key=payload.get("api_key"),
            top_k=top_k,
        )
        if not isinstance(result, dict) or "matches" not in result:
            raise ValueError("dense retrieval returned an invalid response")
        return result

    return await _run_concurrent_requests(
        test_type="retrieval_search",
        concurrency=concurrency,
        iterations=iterations,
        request_factory=_run_search,
        metadata={"retrieval_mode": mode_value if isinstance(mode_value, str) else "dense"},
    )


async def run_document_qa_stress(
    *,
    concurrency: int,
    iterations: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    async def _run_qa() -> dict[str, Any]:
        if not isinstance(payload.get("query"), str) or not payload["query"].strip():
            raise ValueError("payload.query must be a non-empty string")
        if not isinstance(payload.get("provider"), str) or not payload["provider"].strip():
            raise ValueError("payload.provider must be a non-empty string")
        if not isinstance(payload.get("model_name"), str) or not payload["model_name"].strip():
            raise ValueError("payload.model_name must be a non-empty string")

        result = await answer_document_query(
            query=payload["query"],
            provider=payload["provider"],
            model_name=payload["model_name"],
            api_key=payload.get("api_key"),
            retrieval_mode=str(payload.get("retrieval_mode", "hybrid")),
            top_k=int(payload.get("top_k", 5)),
            use_rerank=bool(payload.get("use_rerank", True)),
            rerank_top_k=int(payload.get("rerank_top_k", 5)),
            temperature=float(payload["temperature"]) if payload.get("temperature") is not None else None,
            max_output_tokens=int(payload["max_output_tokens"])
            if payload.get("max_output_tokens") is not None
            else None,
        )
        if not isinstance(result, dict) or "answer" not in result or "citations" not in result:
            raise ValueError("document QA returned an invalid response")
        return result

    return await _run_concurrent_requests(
        test_type="document_qa",
        concurrency=concurrency,
        iterations=iterations,
        request_factory=_run_qa,
        metadata={"retrieval_mode": str(payload.get("retrieval_mode", "hybrid"))},
    )


async def run_stress_test(
    test_type: str,
    concurrency: int,
    iterations: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalized_type = test_type.strip().lower()

    if normalized_type not in ALLOWED_STRESS_TEST_TYPES:
        raise ValueError("test_type must be one of: job_submit, retrieval_search, document_qa")
    if concurrency <= 0:
        raise ValueError("concurrency must be greater than 0")
    if iterations <= 0:
        raise ValueError("iterations must be greater than 0")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    if normalized_type == "job_submit":
        return await run_job_submit_stress(
            concurrency=concurrency,
            iterations=iterations,
            payload=payload,
        )

    if normalized_type == "retrieval_search":
        return await run_retrieval_search_stress(
            concurrency=concurrency,
            iterations=iterations,
            payload=payload,
        )

    return await run_document_qa_stress(
        concurrency=concurrency,
        iterations=iterations,
        payload=payload,
    )