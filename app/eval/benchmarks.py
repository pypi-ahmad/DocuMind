"""Lightweight benchmark definitions for OCR, retrieval, reranking, and QA."""

from app.schemas.eval import BenchmarkCase

BENCHMARK_DESCRIPTIONS: dict[str, str] = {
    "ocr_smoke": "Basic OCR extraction shape and normalization checks",
    "retrieval_smoke": "Dense and hybrid retrieval hit-presence checks",
    "rerank_smoke": "Reranking quality: relevant hit near top",
    "qa_smoke": "Document QA grounding, keyword, and citation checks",
}

# ---------------------------------------------------------------------------
# OCR smoke
# ---------------------------------------------------------------------------

_OCR_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="ocr-shape-default",
        task_type="ocr",
        input={"file_path": "tests/fixtures/sample.png"},
        expected={
            "has_text": True,
            "has_normalized_text": True,
            "has_engine": True,
        },
    ),
    BenchmarkCase(
        case_id="ocr-engine-deepseek",
        task_type="ocr",
        input={"file_path": "tests/fixtures/sample.png", "engine": "deepseek-ocr"},
        expected={
            "engine": "deepseek-ocr",
            "has_text": True,
        },
    ),
    BenchmarkCase(
        case_id="ocr-engine-glm",
        task_type="ocr",
        input={"file_path": "tests/fixtures/sample.png", "engine": "glm-ocr"},
        expected={
            "engine": "glm-ocr",
            "has_text": True,
        },
    ),
    BenchmarkCase(
        case_id="ocr-missing-file",
        task_type="ocr",
        input={"file_path": "nonexistent/missing.png"},
        expected={
            "expect_error": True,
        },
    ),
]

# ---------------------------------------------------------------------------
# Retrieval smoke
# ---------------------------------------------------------------------------

_RETRIEVAL_SEED_DOCS = [
    {
        "doc_id": "eval-doc-1",
        "chunk_id": "eval-doc-1:chunk:0",
        "text": "The annual revenue for FY2025 was $4.2 billion.",
        "vector": [0.1, 0.2, 0.3],
        "metadata": {"source": "annual_report"},
    },
    {
        "doc_id": "eval-doc-1",
        "chunk_id": "eval-doc-1:chunk:1",
        "text": "Operating expenses totaled $1.8 billion in FY2025.",
        "vector": [0.4, 0.5, 0.6],
        "metadata": {"source": "annual_report"},
    },
    {
        "doc_id": "eval-doc-2",
        "chunk_id": "eval-doc-2:chunk:0",
        "text": "The contract effective date is March 1, 2025.",
        "vector": [0.7, 0.8, 0.9],
        "metadata": {"source": "contract"},
    },
]

_RETRIEVAL_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="retrieval-dense-revenue",
        task_type="retrieval",
        input={
            "query": "What was the annual revenue?",
            "mode": "dense",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 3,
        },
        expected={
            "expected_ids": ["eval-doc-1"],
        },
    ),
    BenchmarkCase(
        case_id="retrieval-hybrid-contract",
        task_type="retrieval",
        input={
            "query": "When does the contract start?",
            "mode": "hybrid",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 3,
        },
        expected={
            "expected_ids": ["eval-doc-2"],
        },
    ),
    BenchmarkCase(
        case_id="retrieval-dense-expenses",
        task_type="retrieval",
        input={
            "query": "What are the operating expenses?",
            "mode": "dense",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 2,
        },
        expected={
            "expected_ids": ["eval-doc-1:chunk:1"],
        },
    ),
    BenchmarkCase(
        case_id="retrieval-empty-store",
        task_type="retrieval",
        input={
            "query": "Any query on empty store",
            "mode": "dense",
            "provider": "ollama",
            "model_name": "nomic-embed-text",
            "top_k": 3,
            "skip_seed": True,
        },
        expected={
            "expected_hit_count": 0,
        },
    ),
]

# ---------------------------------------------------------------------------
# Rerank smoke
# ---------------------------------------------------------------------------

_RERANK_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="rerank-relevant-first",
        task_type="rerank",
        input={
            "query": "What is the annual revenue?",
            "hits": [
                {"doc_id": "d1", "chunk_id": "d1:c0", "text": "The weather is sunny today.", "score": 0.9, "metadata": {}},
                {"doc_id": "d2", "chunk_id": "d2:c0", "text": "Annual revenue was $4.2 billion.", "score": 0.5, "metadata": {}},
                {"doc_id": "d3", "chunk_id": "d3:c0", "text": "Employee headcount grew to 5000.", "score": 0.7, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 2,
        },
        expected={
            "top_id": "d2",
            "expected_top_ids": ["d2"],
        },
    ),
    BenchmarkCase(
        case_id="rerank-contract-date",
        task_type="rerank",
        input={
            "query": "When does the contract start?",
            "hits": [
                {"doc_id": "d4", "chunk_id": "d4:c0", "text": "Contract starts on January 15, 2025.", "score": 0.4, "metadata": {}},
                {"doc_id": "d5", "chunk_id": "d5:c0", "text": "The cafeteria menu changed.", "score": 0.8, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 1,
        },
        expected={
            "top_id": "d4",
            "expected_top_ids": ["d4"],
        },
    ),
    BenchmarkCase(
        case_id="rerank-preserves-all",
        task_type="rerank",
        input={
            "query": "financial summary",
            "hits": [
                {"doc_id": "d6", "chunk_id": "d6:c0", "text": "Revenue and profit summary.", "score": 0.6, "metadata": {}},
                {"doc_id": "d7", "chunk_id": "d7:c0", "text": "Market share analysis.", "score": 0.5, "metadata": {}},
            ],
            "provider": "ollama",
            "model_name": "llama3",
            "top_k": 5,
        },
        expected={
            "min_returned": 1,
        },
    ),
]

# ---------------------------------------------------------------------------
# QA smoke
# ---------------------------------------------------------------------------

_QA_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        case_id="qa-dense-revenue",
        task_type="qa",
        input={
            "query": "What was the annual revenue?",
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
    ),
    BenchmarkCase(
        case_id="qa-hybrid-contract",
        task_type="qa",
        input={
            "query": "When does the contract start?",
            "provider": "ollama",
            "model_name": "llama3",
            "retrieval_mode": "hybrid",
            "top_k": 3,
            "use_rerank": True,
            "rerank_top_k": 2,
        },
        expected={
            "expected_keywords": ["March", "2025"],
            "expected_citation_ids": ["eval-doc-2"],
        },
    ),
    BenchmarkCase(
        case_id="qa-empty-store",
        task_type="qa",
        input={
            "query": "What are the expenses?",
            "provider": "ollama",
            "model_name": "llama3",
            "retrieval_mode": "dense",
            "top_k": 3,
            "use_rerank": False,
            "skip_seed": True,
        },
        expected={
            "expect_empty_answer": True,
        },
    ),
    BenchmarkCase(
        case_id="qa-invalid-mode",
        task_type="qa",
        input={
            "query": "Anything",
            "provider": "ollama",
            "model_name": "llama3",
            "retrieval_mode": "sparse",
        },
        expected={
            "expect_error": True,
        },
    ),
]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BENCHMARKS: dict[str, list[BenchmarkCase]] = {
    "ocr_smoke": _OCR_CASES,
    "retrieval_smoke": _RETRIEVAL_CASES,
    "rerank_smoke": _RERANK_CASES,
    "qa_smoke": _QA_CASES,
}

RETRIEVAL_SEED_DOCS = _RETRIEVAL_SEED_DOCS
