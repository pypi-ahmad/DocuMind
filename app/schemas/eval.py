from typing import Any

from pydantic import BaseModel, Field


class BenchmarkCase(BaseModel):
    case_id: str
    task_type: str
    input: dict[str, Any]
    expected: dict[str, Any]


class EvaluationMetric(BaseModel):
    name: str
    value: float | int | str


class EvaluationCaseResult(BaseModel):
    case_id: str
    task_type: str
    success: bool
    latency_ms: float
    metrics: list[EvaluationMetric]
    error: str | None = None
    output_summary: dict[str, Any] | None = None


class EvaluationRunResponse(BaseModel):
    benchmark_name: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    average_latency_ms: float
    results: list[EvaluationCaseResult]
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkInfo(BaseModel):
    name: str
    description: str
    case_count: int


class StressTestRequest(BaseModel):
    test_type: str
    concurrency: int = 5
    iterations: int = 20
    payload: dict[str, Any] = Field(default_factory=dict)


class StressMetric(BaseModel):
    name: str
    value: float | int | str


class StressTestResponse(BaseModel):
    test_type: str
    concurrency: int
    iterations: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_ms: float
    p95_latency_ms: float
    metrics: list[StressMetric] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
