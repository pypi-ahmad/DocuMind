from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path, status

from app.eval.benchmarks import BENCHMARK_DESCRIPTIONS, BENCHMARKS
from app.eval.evaluator import run_benchmark
from app.eval.stress import ALLOWED_STRESS_TEST_TYPES, run_stress_test
from app.schemas.common import ErrorResponse
from app.schemas.eval import (
    BenchmarkInfo,
    EvaluationRunResponse,
    StressTestRequest,
    StressTestResponse,
)

router = APIRouter(prefix="/eval", tags=["evaluation"])

_STRESS_TEST_EXAMPLES = {
    "document_qa": {
        "summary": "Stress test document QA",
        "value": {
            "test_type": "document_qa",
            "concurrency": 5,
            "iterations": 20,
            "payload": {
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


@router.get(
    "/benchmarks",
    response_model=list[BenchmarkInfo],
    summary="List benchmark suites",
    description="Return the benchmark suites available to the internal evaluation harness.",
)
def list_benchmarks() -> list[BenchmarkInfo]:
    return [
        BenchmarkInfo(
            name=name,
            description=BENCHMARK_DESCRIPTIONS.get(name, ""),
            case_count=len(cases),
        )
        for name, cases in BENCHMARKS.items()
    ]


@router.post(
    "/run/{benchmark_name}",
    response_model=EvaluationRunResponse,
    summary="Run a benchmark suite",
    description="Execute a named benchmark suite and return aggregated evaluation results.",
    responses={
        404: {"model": ErrorResponse, "description": "Benchmark suite not found."},
    },
)
async def run_benchmark_route(
    benchmark_name: Annotated[
        str,
        Path(description="Benchmark suite name.", examples=["qa_smoke"]),
    ],
) -> EvaluationRunResponse:
    if benchmark_name not in BENCHMARKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown benchmark: {benchmark_name}",
        )
    result = await run_benchmark(benchmark_name)
    return EvaluationRunResponse(**result)


@router.post(
    "/stress",
    response_model=StressTestResponse,
    summary="Run a stress test",
    description="Execute a concurrent stress test against direct services or job submission paths.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid stress test request."},
    },
)
async def run_stress_route(
    payload: Annotated[StressTestRequest, Body(openapi_examples=_STRESS_TEST_EXAMPLES)],
) -> StressTestResponse:
    normalized_type = payload.test_type.strip().lower()
    if normalized_type not in ALLOWED_STRESS_TEST_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="test_type must be one of: job_submit, retrieval_search, document_qa",
        )
    if payload.concurrency <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="concurrency must be greater than 0",
        )
    if payload.iterations <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="iterations must be greater than 0",
        )

    result = await run_stress_test(
        normalized_type,
        payload.concurrency,
        payload.iterations,
        payload.payload,
    )
    return StressTestResponse(**result)
