"""Tests for the evaluation and benchmark harness."""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.eval.benchmarks import BENCHMARK_DESCRIPTIONS, BENCHMARKS, RETRIEVAL_SEED_DOCS
from app.eval.evaluator import run_benchmark, run_case
from app.eval.metrics import (
    citation_contains_expected,
    hit_contains_expected,
    keyword_match_score,
    safe_average,
)
from app.main import app
from app.schemas.eval import (
    BenchmarkCase,
    BenchmarkInfo,
    EvaluationCaseResult,
    EvaluationMetric,
    EvaluationRunResponse,
)
from app.services import retrieval_store

client = TestClient(app)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestKeywordMatchScore:
    def test_all_present(self) -> None:
        assert keyword_match_score("The revenue was $4.2 billion", ["revenue", "billion"]) == 1.0

    def test_partial(self) -> None:
        assert keyword_match_score("The revenue was high", ["revenue", "billion"]) == 0.5

    def test_none_present(self) -> None:
        assert keyword_match_score("nothing here", ["revenue", "expense"]) == 0.0

    def test_empty_keywords(self) -> None:
        assert keyword_match_score("anything", []) == 1.0

    def test_case_insensitive(self) -> None:
        assert keyword_match_score("REVENUE growth", ["revenue"]) == 1.0


class TestHitContainsExpected:
    def test_all_found(self) -> None:
        hits = [{"doc_id": "d1", "chunk_id": "d1:c0"}, {"doc_id": "d2", "chunk_id": "d2:c0"}]
        assert hit_contains_expected(hits, ["d1", "d2"]) == 1.0

    def test_partial(self) -> None:
        hits = [{"doc_id": "d1", "chunk_id": "d1:c0"}]
        assert hit_contains_expected(hits, ["d1", "d3"]) == 0.5

    def test_empty_hits(self) -> None:
        assert hit_contains_expected([], ["d1"]) == 0.0

    def test_empty_expected(self) -> None:
        assert hit_contains_expected([{"doc_id": "d1"}], []) == 1.0

    def test_chunk_id_match(self) -> None:
        hits = [{"doc_id": "d1", "chunk_id": "d1:c0"}]
        assert hit_contains_expected(hits, ["d1:c0"]) == 1.0


class TestCitationContainsExpected:
    def test_found(self) -> None:
        assert citation_contains_expected([{"doc_id": "d1"}], ["d1"]) == 1.0

    def test_not_found(self) -> None:
        assert citation_contains_expected([{"doc_id": "d1"}], ["d2"]) == 0.0

    def test_empty(self) -> None:
        assert citation_contains_expected([], []) == 1.0


class TestSafeAverage:
    def test_normal(self) -> None:
        assert safe_average([2.0, 4.0]) == 3.0

    def test_empty(self) -> None:
        assert safe_average([]) == 0.0

    def test_single(self) -> None:
        assert safe_average([5.0]) == 5.0


# ---------------------------------------------------------------------------
# Benchmark registry
# ---------------------------------------------------------------------------


class TestBenchmarkRegistry:
    def test_all_benchmarks_defined(self) -> None:
        assert set(BENCHMARKS.keys()) == {"ocr_smoke", "retrieval_smoke", "rerank_smoke", "qa_smoke"}

    def test_each_has_at_least_3_cases(self) -> None:
        for name, cases in BENCHMARKS.items():
            assert len(cases) >= 3, f"{name} has fewer than 3 cases"

    def test_all_have_descriptions(self) -> None:
        for name in BENCHMARKS:
            assert name in BENCHMARK_DESCRIPTIONS
            assert BENCHMARK_DESCRIPTIONS[name]

    def test_seed_docs_defined(self) -> None:
        assert len(RETRIEVAL_SEED_DOCS) >= 2
        for doc in RETRIEVAL_SEED_DOCS:
            assert "doc_id" in doc
            assert "text" in doc
            assert "vector" in doc


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestEvalSchemas:
    def test_benchmark_case(self) -> None:
        bc = BenchmarkCase(case_id="t1", task_type="ocr", input={"a": 1}, expected={"b": 2})
        assert bc.case_id == "t1"

    def test_evaluation_metric(self) -> None:
        em = EvaluationMetric(name="kw", value=0.9)
        assert em.value == 0.9
        em_str = EvaluationMetric(name="check", value="PASS")
        assert em_str.value == "PASS"

    def test_case_result_defaults(self) -> None:
        cr = EvaluationCaseResult(
            case_id="x", task_type="ocr", success=True, latency_ms=1.0, metrics=[]
        )
        assert cr.error is None
        assert cr.output_summary is None

    def test_run_response(self) -> None:
        rr = EvaluationRunResponse(
            benchmark_name="test",
            total_cases=1,
            passed_cases=1,
            failed_cases=0,
            average_latency_ms=1.0,
            results=[],
            metadata={},
        )
        assert rr.benchmark_name == "test"

    def test_benchmark_info(self) -> None:
        bi = BenchmarkInfo(name="n", description="d", case_count=3)
        assert bi.case_count == 3


# ---------------------------------------------------------------------------
# Evaluator – run_case with unknown task_type
# ---------------------------------------------------------------------------


class TestRunCase:
    def test_unknown_task_type(self) -> None:
        case = BenchmarkCase(case_id="bad", task_type="unknown", input={}, expected={})
        result = asyncio.run(run_case(case))
        assert result.success is False
        assert "Unknown task_type" in (result.error or "")

    def test_ocr_expected_error(self) -> None:
        case = BenchmarkCase(
            case_id="ocr-err",
            task_type="ocr",
            input={"file_path": "nonexistent/file.png"},
            expected={"expect_error": True},
        )
        result = asyncio.run(run_case(case))
        assert result.success is True
        metric_names = [m.name for m in result.metrics]
        assert "expected_error" in metric_names

    def test_retrieval_empty_store(self) -> None:
        prior = retrieval_store.get_records()
        retrieval_store.clear_store()
        fake_search = AsyncMock(return_value={"query": "anything", "matches": []})
        try:
            case = BenchmarkCase(
                case_id="ret-empty",
                task_type="retrieval",
                input={
                    "query": "anything",
                    "mode": "dense",
                    "provider": "ollama",
                    "model_name": "nomic-embed-text",
                    "top_k": 3,
                    "skip_seed": True,
                },
                expected={"expected_hit_count": 0},
            )
            with patch("app.eval.evaluator.search_similar", fake_search):
                result = asyncio.run(run_case(case))
            assert result.success is True
            assert any(m.name == "hit_count_match" and m.value == "PASS" for m in result.metrics)
        finally:
            retrieval_store.clear_store()
            if prior:
                retrieval_store.add_documents(prior)

    def test_qa_expected_error(self) -> None:
        case = BenchmarkCase(
            case_id="qa-invalid",
            task_type="qa",
            input={
                "query": "anything",
                "provider": "ollama",
                "model_name": "llama3",
                "retrieval_mode": "sparse",
            },
            expected={"expect_error": True},
        )
        result = asyncio.run(run_case(case))
        assert result.success is True

    def test_rerank_with_mock(self) -> None:
        fake_result = {
            "query": "test",
            "hits": [
                {
                    "doc_id": "d2",
                    "chunk_id": "d2:c0",
                    "text": "Annual revenue",
                    "original_score": 0.5,
                    "rerank_score": 0.95,
                    "final_score": 0.9,
                    "metadata": {},
                }
            ],
            "metadata": {"returned": 1},
        }
        case = BenchmarkCase(
            case_id="rerank-mock",
            task_type="rerank",
            input={
                "query": "revenue",
                "hits": [
                    {"doc_id": "d1", "chunk_id": "d1:c0", "text": "Weather is nice", "score": 0.9, "metadata": {}},
                    {"doc_id": "d2", "chunk_id": "d2:c0", "text": "Annual revenue", "score": 0.5, "metadata": {}},
                ],
                "provider": "ollama",
                "model_name": "llama3",
                "top_k": 1,
            },
            expected={"top_id": "d2", "expected_top_ids": ["d2"]},
        )
        with patch("app.eval.evaluator.rerank_hits", new_callable=AsyncMock, return_value=fake_result):
            result = asyncio.run(run_case(case))
        assert result.success is True
        assert any(m.name == "top_id_match" and m.value == "PASS" for m in result.metrics)

    def test_qa_with_mock(self) -> None:
        fake_qa = {
            "query": "revenue?",
            "answer": "The annual revenue was $4.2 billion.",
            "citations": [{"doc_id": "eval-doc-1", "chunk_id": "eval-doc-1:chunk:0", "text": "...", "metadata": {}}],
            "retrieval_mode": "dense",
            "used_rerank": False,
            "metadata": {},
        }
        case = BenchmarkCase(
            case_id="qa-mock",
            task_type="qa",
            input={
                "query": "revenue?",
                "provider": "ollama",
                "model_name": "llama3",
                "retrieval_mode": "dense",
                "top_k": 3,
                "use_rerank": False,
            },
            expected={
                "expected_keywords": ["revenue", "4.2", "billion"],
                "expected_citation_ids": ["eval-doc-1"],
            },
        )
        with patch("app.eval.evaluator.answer_document_query", new_callable=AsyncMock, return_value=fake_qa):
            result = asyncio.run(run_case(case))
        assert result.success is True
        assert any(m.name == "keyword_score" for m in result.metrics)
        assert any(m.name == "citation_recall" for m in result.metrics)


# ---------------------------------------------------------------------------
# Evaluator – run_benchmark
# ---------------------------------------------------------------------------


class TestRunBenchmark:
    def test_unknown_benchmark(self) -> None:
        with pytest.raises(KeyError, match="Unknown benchmark"):
            asyncio.run(run_benchmark("nonexistent"))

    def test_partial_failure_still_returns(self) -> None:
        result = asyncio.run(run_benchmark("ocr_smoke"))
        assert result["benchmark_name"] == "ocr_smoke"
        assert result["total_cases"] == len(BENCHMARKS["ocr_smoke"])
        assert result["passed_cases"] + result["failed_cases"] == result["total_cases"]
        assert isinstance(result["average_latency_ms"], float)
        assert len(result["results"]) == result["total_cases"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class TestEvalRoutes:
    def test_get_benchmarks(self) -> None:
        resp = client.get("/eval/benchmarks")
        assert resp.status_code == 200
        body = resp.json()
        names = {b["name"] for b in body}
        assert names == {"ocr_smoke", "retrieval_smoke", "rerank_smoke", "qa_smoke"}
        for b in body:
            assert b["case_count"] >= 3
            assert b["description"]

    def test_unknown_benchmark_404(self) -> None:
        resp = client.post("/eval/run/nonexistent")
        assert resp.status_code == 404

    def test_run_ocr_smoke_returns_valid_shape(self) -> None:
        resp = client.post("/eval/run/ocr_smoke")
        assert resp.status_code == 200
        body = resp.json()
        assert body["benchmark_name"] == "ocr_smoke"
        assert body["total_cases"] >= 3
        assert "results" in body
        assert "metadata" in body
        assert body["passed_cases"] + body["failed_cases"] == body["total_cases"]
        for r in body["results"]:
            assert "case_id" in r
            assert "task_type" in r
            assert "success" in r
            assert "latency_ms" in r
            assert "metrics" in r
