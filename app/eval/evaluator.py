"""Evaluation engine: dispatches benchmark cases to existing services and collects metrics."""

import time
from typing import Any

from app.eval.benchmarks import (
    BENCHMARK_DESCRIPTIONS,
    BENCHMARKS,
    RETRIEVAL_SEED_DOCS,
)
from app.eval.metrics import (
    citation_contains_expected,
    hit_contains_expected,
    keyword_match_score,
    safe_average,
)
from app.schemas.eval import BenchmarkCase, EvaluationCaseResult, EvaluationMetric
from app.services import retrieval_store
from app.services.document_qa import answer_document_query
from app.services.embedding_service import search_similar
from app.services.hybrid_retrieval import hybrid_search
from app.services.indexing import extract_ocr_document
from app.services.reranker import rerank_hits


async def _run_ocr_case(case: BenchmarkCase) -> EvaluationCaseResult:
    start = time.perf_counter()
    error: str | None = None
    metrics: list[EvaluationMetric] = []
    output_summary: dict[str, Any] = {}
    success = False

    try:
        engine_name, ocr_result = await extract_ocr_document(
            file_path=case.input["file_path"],
            ocr_engine=case.input.get("engine"),
            prefer_structure=case.input.get("prefer_structure", False),
        )

        raw_text = ocr_result.get("text", "")
        normalized_text = ocr_result.get("normalized_text", "")

        output_summary = {
            "engine": engine_name,
            "text_length": len(raw_text),
            "normalized_text_length": len(normalized_text),
            "text_preview": raw_text[:200] if raw_text else "",
        }

        expected = case.expected
        checks_passed = True

        if expected.get("has_text") and not raw_text.strip():
            checks_passed = False
            metrics.append(EvaluationMetric(name="has_text", value="FAIL"))
        elif expected.get("has_text"):
            metrics.append(EvaluationMetric(name="has_text", value="PASS"))

        if expected.get("has_normalized_text") and not normalized_text.strip():
            checks_passed = False
            metrics.append(EvaluationMetric(name="has_normalized_text", value="FAIL"))
        elif expected.get("has_normalized_text"):
            metrics.append(EvaluationMetric(name="has_normalized_text", value="PASS"))

        if expected.get("has_engine") and not engine_name:
            checks_passed = False
            metrics.append(EvaluationMetric(name="has_engine", value="FAIL"))
        elif expected.get("has_engine"):
            metrics.append(EvaluationMetric(name="has_engine", value="PASS"))

        if "engine" in expected and engine_name != expected["engine"]:
            checks_passed = False
            metrics.append(EvaluationMetric(name="engine_match", value="FAIL"))
        elif "engine" in expected:
            metrics.append(EvaluationMetric(name="engine_match", value="PASS"))

        success = checks_passed

    except Exception as exc:
        error = str(exc)
        if case.expected.get("expect_error"):
            success = True
            metrics.append(EvaluationMetric(name="expected_error", value="PASS"))
        else:
            metrics.append(EvaluationMetric(name="unexpected_error", value=str(exc)[:200]))

    elapsed_ms = (time.perf_counter() - start) * 1000
    return EvaluationCaseResult(
        case_id=case.case_id,
        task_type=case.task_type,
        success=success,
        latency_ms=round(elapsed_ms, 2),
        metrics=metrics,
        error=error,
        output_summary=output_summary or None,
    )


def _seed_retrieval_store() -> list[dict[str, Any]]:
    """Seed the retrieval store with benchmark documents, returning prior state."""
    prior = retrieval_store.get_records()
    retrieval_store.add_documents(RETRIEVAL_SEED_DOCS)
    return prior


def _restore_retrieval_store(prior_records: list[dict[str, Any]]) -> None:
    """Restore retrieval store to its prior state."""
    retrieval_store.clear_store()
    if prior_records:
        retrieval_store.add_documents(prior_records)


async def _run_retrieval_case(case: BenchmarkCase) -> EvaluationCaseResult:
    start = time.perf_counter()
    error: str | None = None
    metrics: list[EvaluationMetric] = []
    output_summary: dict[str, Any] = {}
    success = False
    skip_seed = case.input.get("skip_seed", False)

    prior: list[dict[str, Any]] = []
    try:
        if not skip_seed:
            prior = _seed_retrieval_store()

        mode = case.input.get("mode", "dense")
        query = case.input["query"]
        provider = case.input["provider"]
        model_name = case.input["model_name"]
        top_k = case.input.get("top_k", 5)

        if mode == "dense":
            result = await search_similar(
                query=query,
                provider=provider,
                model_name=model_name,
                top_k=top_k,
            )
            hits = result.get("matches", [])
        else:
            result = await hybrid_search(
                query=query,
                provider=provider,
                model_name=model_name,
                top_k=top_k,
            )
            hits = result.get("hits", [])

        hit_ids = [h.get("doc_id", "") for h in hits]
        chunk_ids = [h.get("chunk_id", "") for h in hits]

        output_summary = {
            "mode": mode,
            "hit_count": len(hits),
            "top_doc_ids": hit_ids[:5],
            "top_chunk_ids": chunk_ids[:5],
        }

        expected = case.expected

        if "expected_hit_count" in expected:
            actual_count = len(hits)
            count_ok = actual_count == expected["expected_hit_count"]
            metrics.append(EvaluationMetric(name="hit_count_match", value="PASS" if count_ok else "FAIL"))
            metrics.append(EvaluationMetric(name="actual_hit_count", value=actual_count))
            success = count_ok
        elif "expected_ids" in expected:
            score = hit_contains_expected(hits, expected["expected_ids"])
            metrics.append(EvaluationMetric(name="hit_id_recall", value=round(score, 3)))
            success = score >= 1.0
        else:
            success = len(hits) > 0

    except Exception as exc:
        error = str(exc)
        if case.expected.get("expect_error"):
            success = True
            metrics.append(EvaluationMetric(name="expected_error", value="PASS"))
        else:
            metrics.append(EvaluationMetric(name="unexpected_error", value=str(exc)[:200]))
    finally:
        if not skip_seed:
            _restore_retrieval_store(prior)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return EvaluationCaseResult(
        case_id=case.case_id,
        task_type=case.task_type,
        success=success,
        latency_ms=round(elapsed_ms, 2),
        metrics=metrics,
        error=error,
        output_summary=output_summary or None,
    )


async def _run_rerank_case(case: BenchmarkCase) -> EvaluationCaseResult:
    start = time.perf_counter()
    error: str | None = None
    metrics: list[EvaluationMetric] = []
    output_summary: dict[str, Any] = {}
    success = False

    try:
        result = await rerank_hits(
            query=case.input["query"],
            hits=case.input["hits"],
            provider=case.input["provider"],
            model_name=case.input["model_name"],
            top_k=case.input.get("top_k", 5),
        )

        reranked = result.get("hits", [])
        reranked_ids = [h.get("doc_id", "") for h in reranked]

        output_summary = {
            "reranked_count": len(reranked),
            "top_reranked_ids": reranked_ids[:5],
        }

        expected = case.expected
        checks_passed = True

        if "top_id" in expected and reranked:
            top_match = reranked[0].get("doc_id") == expected["top_id"]
            metrics.append(EvaluationMetric(name="top_id_match", value="PASS" if top_match else "FAIL"))
            if not top_match:
                checks_passed = False

        if "expected_top_ids" in expected:
            score = hit_contains_expected(reranked, expected["expected_top_ids"])
            metrics.append(EvaluationMetric(name="top_id_recall", value=round(score, 3)))
            if score < 1.0:
                checks_passed = False

        if "min_returned" in expected:
            enough = len(reranked) >= expected["min_returned"]
            metrics.append(EvaluationMetric(name="min_returned", value="PASS" if enough else "FAIL"))
            if not enough:
                checks_passed = False

        success = checks_passed

    except Exception as exc:
        error = str(exc)
        if case.expected.get("expect_error"):
            success = True
            metrics.append(EvaluationMetric(name="expected_error", value="PASS"))
        else:
            metrics.append(EvaluationMetric(name="unexpected_error", value=str(exc)[:200]))

    elapsed_ms = (time.perf_counter() - start) * 1000
    return EvaluationCaseResult(
        case_id=case.case_id,
        task_type=case.task_type,
        success=success,
        latency_ms=round(elapsed_ms, 2),
        metrics=metrics,
        error=error,
        output_summary=output_summary or None,
    )


async def _run_qa_case(case: BenchmarkCase) -> EvaluationCaseResult:
    start = time.perf_counter()
    error: str | None = None
    metrics: list[EvaluationMetric] = []
    output_summary: dict[str, Any] = {}
    success = False
    skip_seed = case.input.get("skip_seed", False)

    prior: list[dict[str, Any]] = []
    try:
        if not skip_seed:
            prior = _seed_retrieval_store()

        result = await answer_document_query(
            query=case.input["query"],
            provider=case.input["provider"],
            model_name=case.input["model_name"],
            retrieval_mode=case.input.get("retrieval_mode", "hybrid"),
            top_k=case.input.get("top_k", 5),
            use_rerank=case.input.get("use_rerank", True),
            rerank_top_k=case.input.get("rerank_top_k", 5),
        )

        answer = result.get("answer", "")
        citations = result.get("citations", [])

        output_summary = {
            "answer_preview": answer[:300] if answer else "",
            "citation_count": len(citations),
            "citation_doc_ids": [c.get("doc_id", "") for c in citations][:5],
            "retrieval_mode": result.get("retrieval_mode", ""),
            "used_rerank": result.get("used_rerank", False),
        }

        expected = case.expected
        checks_passed = True

        if expected.get("expect_empty_answer"):
            is_empty = "No indexed content" in answer or not citations
            metrics.append(EvaluationMetric(name="empty_answer", value="PASS" if is_empty else "FAIL"))
            if not is_empty:
                checks_passed = False
        else:
            if "expected_keywords" in expected:
                kw_score = keyword_match_score(answer, expected["expected_keywords"])
                metrics.append(EvaluationMetric(name="keyword_score", value=round(kw_score, 3)))
                if kw_score < 0.5:
                    checks_passed = False

            if "expected_citation_ids" in expected:
                cit_score = citation_contains_expected(citations, expected["expected_citation_ids"])
                metrics.append(EvaluationMetric(name="citation_recall", value=round(cit_score, 3)))
                if cit_score < 1.0:
                    checks_passed = False

        success = checks_passed

    except Exception as exc:
        error = str(exc)
        if case.expected.get("expect_error"):
            success = True
            metrics.append(EvaluationMetric(name="expected_error", value="PASS"))
        else:
            metrics.append(EvaluationMetric(name="unexpected_error", value=str(exc)[:200]))
    finally:
        if not skip_seed:
            _restore_retrieval_store(prior)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return EvaluationCaseResult(
        case_id=case.case_id,
        task_type=case.task_type,
        success=success,
        latency_ms=round(elapsed_ms, 2),
        metrics=metrics,
        error=error,
        output_summary=output_summary or None,
    )


_DISPATCHERS = {
    "ocr": _run_ocr_case,
    "retrieval": _run_retrieval_case,
    "rerank": _run_rerank_case,
    "qa": _run_qa_case,
}


async def run_case(case: BenchmarkCase) -> EvaluationCaseResult:
    dispatcher = _DISPATCHERS.get(case.task_type)
    if dispatcher is None:
        return EvaluationCaseResult(
            case_id=case.case_id,
            task_type=case.task_type,
            success=False,
            latency_ms=0.0,
            metrics=[],
            error=f"Unknown task_type: {case.task_type}",
        )
    return await dispatcher(case)


async def run_benchmark(benchmark_name: str) -> dict[str, Any]:
    cases = BENCHMARKS.get(benchmark_name)
    if cases is None:
        raise KeyError(f"Unknown benchmark: {benchmark_name}")

    results: list[EvaluationCaseResult] = []
    for case in cases:
        result = await run_case(case)
        results.append(result)

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    latencies = [r.latency_ms for r in results]

    return {
        "benchmark_name": benchmark_name,
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": failed,
        "average_latency_ms": round(safe_average(latencies), 2),
        "results": [r.model_dump() for r in results],
        "metadata": {
            "description": BENCHMARK_DESCRIPTIONS.get(benchmark_name, ""),
        },
    }
