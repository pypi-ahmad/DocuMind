# DocuMind — Usage Guide

> Document intelligence platform — extract, structure, index, and query documents through a unified API and web interface.

---

## Purpose

DocuMind is an OCR-first document intelligence system. It extracts text from images and PDFs using local OCR models, optionally post-processes that text with LLMs, indexes it into a vector store, and supports retrieval-augmented question answering — all through a single FastAPI backend and a React frontend.

Every capability is available as both a direct API call and (for most operations) a background job.

---

## Who This App Is For

- **Developers** building document processing pipelines who need a self-hosted, local-first OCR and RAG backend.
- **Teams** evaluating OCR accuracy, retrieval quality, or LLM providers against their own documents.
- **Individual users** who want to extract text from scanned documents, summarize them, or ask questions about a collection of indexed files — without sending data to third-party services (when using Ollama).

---

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [Setup & Installation](#2-setup--installation)
3. [Starting the App](#3-starting-the-app)
4. [Main Workflow — Step by Step](#4-main-workflow--step-by-step)
5. [Health & Status](#5-health--status)
6. [Provider Configuration](#6-provider-configuration)
7. [OCR Extraction](#7-ocr-extraction)
8. [OCR Post-Processing](#8-ocr-post-processing)
9. [Text Generation](#9-text-generation)
10. [Embedding Generation](#10-embedding-generation)
11. [Document Indexing](#11-document-indexing)
12. [Search & Retrieval](#12-search--retrieval)
13. [Document QA](#13-document-qa)
14. [Pipelines](#14-pipelines)
15. [Background Jobs](#15-background-jobs)
16. [Evaluation & Stress Testing](#16-evaluation--stress-testing)
17. [Authentication](#17-authentication)
18. [Web UI](#18-web-ui)
19. [Input Expectations](#19-input-expectations)
20. [Output & Result Behavior](#20-output--result-behavior)
21. [Error States & Troubleshooting](#21-error-states--troubleshooting)
22. [Limitations & Important Notes](#22-limitations--important-notes)
23. [Configuration Reference](#23-configuration-reference)

---

## 1. Before You Start

### Required

| Dependency | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12+ | Backend runtime |
| **pip** | — | Package installation (`pip install -e ".[dev]"`) |

### Optional

| Dependency | Version | Purpose |
|------------|---------|---------|
| **Node.js** | 18+ | Required only if you want the web UI |
| **Ollama** | latest | Required only for local OCR (`deepseek-ocr`, `glm-ocr`) and local LLM inference |
| **Milvus** | 2.x | Persistent vector storage (default is in-memory) |
| **Redis** | 6+ | Persistent job queue (default is in-memory) |

### Cloud provider accounts (optional)

If you plan to use cloud LLMs or cloud embeddings, you need an API key for at least one of:

| Provider | Capabilities | Key variable |
|----------|-------------|--------------|
| OpenAI | Text generation, embeddings | `OPENAI_API_KEY` |
| Google Gemini | Text generation, embeddings | `GEMINI_API_KEY` |
| Anthropic | Text generation only | `ANTHROPIC_API_KEY` |

Keys can be set in `.env` or passed per-request via the `api_key` field (BYOK).

---

## 2. Setup & Installation

### Backend

```bash
# Clone and enter the project
git clone https://github.com/pypi-ahmad/DocuMind.git
cd DocuMind

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell

# Install dependencies (includes dev/test tooling)
pip install -e ".[dev]"

# Copy the example environment file and edit as needed
cp .env.example .env               # macOS / Linux
Copy-Item .env.example .env        # Windows PowerShell
```

### Frontend

```bash
cd ui
npm install
```

### Ollama OCR models (if using local OCR)

```bash
ollama pull deepseek-ocr:3b    # General-purpose OCR
ollama pull glm-ocr             # Structured-output OCR (headings, lists, tables)
```

Default Ollama URL: `http://localhost:11434` (configurable via `DOCUMIND_OLLAMA_BASE_URL`).

---

## 3. Starting the App

### Backend

```bash
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend

```bash
cd ui
npm run dev
```

- Web UI: `http://localhost:5173`
- Set `VITE_API_BASE_URL` in `ui/.env` if the backend runs on a different host or port.

### Verify

```bash
curl http://localhost:8000/health/live
# → {"status": "ok"}
```

---

## 4. Main Workflow — Step by Step

The most common end-to-end flow is: **upload a document → extract text → index it → ask questions**.

### Step 1 — Upload a document

```bash
curl -X POST http://localhost:8000/ocr/upload \
  -F "file=@/path/to/document.pdf"
# → {"file_path": "/tmp/.../a1b2c3d4.pdf"}
```

### Step 2 — Extract text via OCR

```bash
curl -X POST http://localhost:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/tmp/.../a1b2c3d4.pdf", "prefer_structure": true}'
```

### Step 3 — Index the document

```bash
curl -X POST http://localhost:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "my-document",
    "file_path": "/tmp/.../a1b2c3d4.pdf",
    "embedding_provider": "openai",
    "embedding_model_name": "text-embedding-3-small",
    "api_key": "sk-..."
  }'
```

### Step 4 — Ask a question

```bash
curl -X POST http://localhost:8000/retrieval/qa \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the payment terms?",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "retrieval_mode": "hybrid",
    "use_rerank": true
  }'
```

The response includes the answer and `citations` linking back to specific document chunks.

> **Web UI shortcut:** The frontend "Ask Your Documents" preset handles steps 3–4 automatically. The "Index Document" preset handles upload + indexing.

---

## 5. Health & Status

```bash
# Liveness — confirms the process is running
curl http://localhost:8000/health/live
# → {"status": "ok"}

# Readiness — checks queue, model manager, and optional backends
curl http://localhost:8000/health/ready
# → {"status": "ok", "checks": {"queue_initialized": "ok", "model_manager_accessible": "ok"}}
# → status is "degraded" if any check reports "error"

# Legacy health endpoint
curl http://localhost:8000/health
# → {"status": "ok"}

# Application metadata
curl http://localhost:8000/info
# → {"app_name": "DocuMind", "version": "0.1.0", "python_version": "...",
#    "supported_providers": [...], "supported_ocr_engines": [...]}
```

When Redis or Milvus backends are configured, `/health/ready` also checks their connectivity and adds `"redis"` or `"milvus"` keys to the `checks` object.

---

## 6. Provider Configuration

### List all providers

```bash
curl http://localhost:8000/providers
```

Each provider includes `requires_api_key`, `supports_byok`, and `has_env_key` flags.

### List models for a provider

```bash
# Ollama (no key needed)
curl -X POST http://localhost:8000/providers/ollama/models \
  -H "Content-Type: application/json" \
  -d '{}'

# Cloud provider (BYOK)
curl -X POST http://localhost:8000/providers/openai/models \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-..."}'
```

### Provider capabilities

| Provider | Requires API Key | Text Generation | Embeddings | BYOK |
|----------|:----------------:|:---------------:|:----------:|:----:|
| **Ollama** | No | ✓ | ✓ | — |
| **OpenAI** | Yes | ✓ | ✓ | ✓ |
| **Gemini** | Yes | ✓ | ✓ | ✓ |
| **Anthropic** | Yes | ✓ | — | ✓ |

### BYOK (Bring Your Own Key)

Cloud providers accept an `api_key` field on every request. When supplied, it overrides any server-side environment variable for that single request. Keys passed via BYOK are never persisted to disk.

### Ollama runtime management

```bash
# Check active model status
curl http://localhost:8000/runtime/status

# Activate a model (downloads and loads it into memory)
curl -X POST http://localhost:8000/runtime/activate \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "model_name": "llama3"}'

# Deactivate the current model
curl -X POST http://localhost:8000/runtime/deactivate \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 7. OCR Extraction

Extract text from images or multi-page PDFs using local Ollama-hosted OCR models.

### Supported file formats

`.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf`

### Upload a file

```bash
curl -X POST http://localhost:8000/ocr/upload \
  -F "file=@/path/to/document.pdf"
# → {"file_path": "/tmp/.../a1b2c3d4.pdf"}
```

- Max file size: 50 MB (configurable via `DOCUMIND_MAX_UPLOAD_SIZE_MB`)
- Files are stored with a UUID filename in the upload directory
- Automatic cleanup after 60 minutes (configurable via `DOCUMIND_UPLOAD_TTL_MINUTES`)

### Run extraction

```bash
curl -X POST http://localhost:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/tmp/.../a1b2c3d4.pdf",
    "prefer_structure": true
  }'
```

### Parameters

| Field | Type | Required | Default | Description |
|-------|------|:--------:|---------|-------------|
| `file_path` | string | ✓ | — | Absolute path to the file on the server |
| `engine` | string | | auto | `"deepseek-ocr"` or `"glm-ocr"` |
| `prefer_structure` | bool | | `false` | Preserve document structure (headings, lists, tables) |

### Engine selection

| Engine | Model | Best for |
|--------|-------|----------|
| `deepseek-ocr` | `deepseek-ocr:3b` | General-purpose extraction (default) |
| `glm-ocr` | `glm-ocr` | Structured documents with headings, tables, lists |

When `engine` is omitted: `prefer_structure=true` selects `glm-ocr`, otherwise `deepseek-ocr`.

### Preview engine routing (without running OCR)

```bash
curl -X POST http://localhost:8000/ocr/route \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/document.png"}'
```

### Response shape

```json
{
  "engine": "glm-ocr",
  "text": "...merged text across all pages...",
  "normalized_text": "...cleaned and normalized text...",
  "normalization": {
    "removed_blank_lines": 4,
    "collapsed_whitespace": true,
    "merged_broken_lines": true,
    "cleaned_hyphenation": false
  },
  "structured": {},
  "layout": {"pages": 3, "structure": true},
  "tables": [],
  "confidence": 0.0,
  "metadata": {"model": "glm-ocr"},
  "pages": [
    {"page": 1, "text": "...", "confidence": 0.0, "metadata": {}},
    {"page": 2, "text": "...", "confidence": 0.0, "metadata": {}}
  ]
}
```

**Multi-page PDFs:** Each page is processed independently. The `pages` array contains per-page results; the top-level `text` is the merged output of all pages.

---

## 8. OCR Post-Processing

Run an LLM over extracted OCR text to clean it up, summarize it, or extract structured fields.

```bash
curl -X POST http://localhost:8000/ocr/postprocess \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summary",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "ocr_result": { "...full OCR response from /ocr/extract..." }
  }'
```

### Parameters

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `ocr_result` | object | ✓ | The full JSON response from `/ocr/extract` |
| `task` | string | ✓ | One of: `"cleanup"`, `"summary"`, `"extract_key_fields"` |
| `provider` | string | ✓ | LLM provider (`"ollama"`, `"openai"`, `"gemini"`, `"anthropic"`) |
| `model_name` | string | ✓ | Model to use for post-processing |
| `api_key` | string | | BYOK for cloud providers |
| `temperature` | float | | Sampling temperature (≥ 0) |
| `max_output_tokens` | int | | Maximum response length in tokens |

### Available tasks

| Task | What it does |
|------|-------------|
| `cleanup` | Fixes OCR artifacts, normalizes whitespace and word boundaries |
| `summary` | Produces a concise factual summary of the document |
| `extract_key_fields` | Extracts structured key-value pairs (names, dates, amounts, IDs) |

### Response shape

```json
{
  "task": "summary",
  "provider": "openai",
  "model_name": "gpt-4o-mini",
  "output_text": "This invoice is for...",
  "usage": {"input_tokens": 312, "output_tokens": 80},
  "metadata": {}
}
```

---

## 9. Text Generation

Call any supported LLM directly, without going through OCR or retrieval.

```bash
curl -X POST http://localhost:8000/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model_name": "llama3",
    "prompt": "Explain retrieval-augmented generation in two sentences.",
    "temperature": 0.3
  }'
```

### Parameters

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `provider` | string | ✓ | `"ollama"`, `"openai"`, `"gemini"`, or `"anthropic"` |
| `model_name` | string | ✓ | Model name |
| `prompt` | string | ✓ | Text prompt |
| `api_key` | string | | BYOK for cloud providers |
| `temperature` | float | | Sampling temperature |
| `max_output_tokens` | int | | Token budget for the response (default: `1024`) |

> **Note:** Text generation cannot be submitted as a background job. It is direct-only.

---

## 10. Embedding Generation

Generate vector embeddings for one or more text inputs.

```bash
curl -X POST http://localhost:8000/embeddings/generate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "input_texts": ["What are the payment terms in this contract?"],
    "api_key": "sk-..."
  }'
```

### Parameters

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `provider` | string | ✓ | Provider that supports embeddings |
| `model_name` | string | ✓ | Embedding model name |
| `input_texts` | string[] | ✓ | One or more texts to embed (minimum 1) |
| `api_key` | string | | BYOK for cloud providers |

### Response shape

```json
{
  "provider": "openai",
  "model_name": "text-embedding-3-small",
  "vectors": [
    {"index": 0, "vector": [0.012, -0.034, ...]}
  ],
  "metadata": {}
}
```

> **Note:** Anthropic does not support embedding generation. Use Ollama, OpenAI, or Gemini.

---

## 11. Document Indexing

Documents must be indexed before they can be searched or queried via QA. Indexing splits text into chunks, generates embeddings, and stores them in the vector store.

### Index plain text

```bash
curl -X POST http://localhost:8000/retrieval/index \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "contract-2024",
    "text": "This agreement is entered into on January 1 2024...",
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "metadata": {"source": "contracts", "year": 2024}
  }'
```

### Index from a file (OCR + chunk + embed in one call)

```bash
curl -X POST http://localhost:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "invoice-001",
    "file_path": "/path/to/invoice.pdf",
    "embedding_provider": "openai",
    "embedding_model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "ocr_engine": "glm-ocr",
    "prefer_structure": true,
    "metadata": {"type": "invoice", "vendor": "Acme"}
  }'
```

### Parameters (index-ocr)

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `doc_id` | string | ✓ | Unique document identifier (your choice) |
| `file_path` | string | ✓ | Absolute path to the file on the server |
| `embedding_provider` | string | ✓ | Provider for embedding generation |
| `embedding_model_name` | string | ✓ | Embedding model name |
| `api_key` | string | | BYOK API key |
| `ocr_engine` | string | | Override engine selection |
| `prefer_structure` | bool | | Request structured OCR output |
| `metadata` | object | | Arbitrary metadata attached to all chunks |

Each chunk is stored with an auto-generated `chunk_id` in the format `{doc_id}:chunk:{i}` (e.g., `invoice-001:chunk:0`, `invoice-001:chunk:1`).

### List indexed documents

```bash
curl http://localhost:8000/retrieval/documents
```

Returns an array of objects, each with `doc_id`, `chunk_count`, and `metadata`.

### Remove a single indexed document

```bash
curl -X DELETE http://localhost:8000/retrieval/documents/{doc_id}
```

Returns HTTP 204 on success. Returns HTTP 404 if no document matching `doc_id` exists in the index. All chunks belonging to that document are removed.

### Clear all indexed documents

```bash
curl -X DELETE http://localhost:8000/retrieval/documents
```

Returns HTTP 204. Removes every chunk from the active vector store.

---

## 12. Search & Retrieval

### Dense vector search

Semantic similarity using embeddings only.

```bash
curl -X POST http://localhost:8000/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment terms",
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "top_k": 5
  }'
```

### Hybrid search (dense + BM25)

Combines vector similarity with keyword matching.

```bash
curl -X POST http://localhost:8000/retrieval/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment terms",
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "top_k": 5,
    "dense_weight": 0.6,
    "sparse_weight": 0.4
  }'
```

| Field | Default | Description |
|-------|---------|-------------|
| `dense_weight` | `0.5` | Weight for vector semantic similarity |
| `sparse_weight` | `0.5` | Weight for BM25 keyword matching |

Both weights must be non-negative and at least one must be greater than zero.

### Rerank results

Re-score candidate hits using LLM-based relevance judgment:

```bash
curl -X POST http://localhost:8000/retrieval/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment terms",
    "hits": [{"doc_id": "...", "chunk_id": "...", "text": "...", "score": 0.9}],
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "top_k": 3
  }'
```

Returns hits with `original_score`, `rerank_score`, and `final_score` fields.

---

## 13. Document QA

Ask a question grounded in indexed documents. Retrieval, optional reranking, and answer generation happen in a single call.

```bash
curl -X POST http://localhost:8000/retrieval/qa \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the total on invoice 001?",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "retrieval_mode": "hybrid",
    "top_k": 5,
    "use_rerank": true,
    "rerank_top_k": 3,
    "temperature": 0.1
  }'
```

### Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | — | The question to answer (required) |
| `provider` | string | — | LLM provider (required) |
| `model_name` | string | — | Model for answer generation (required) |
| `api_key` | string | — | BYOK for cloud providers |
| `retrieval_mode` | string | `"hybrid"` | `"dense"` or `"hybrid"` |
| `top_k` | int | `5` | Number of candidate chunks to retrieve |
| `use_rerank` | bool | `true` | Apply LLM reranking before answering |
| `rerank_top_k` | int | `5` | Chunks to keep after reranking |
| `temperature` | float | — | Sampling temperature for answer generation |
| `max_output_tokens` | int | — | Token budget for the answer |

### Response shape

```json
{
  "query": "What is the total on invoice 001?",
  "answer": "The total amount is $4,250.00.",
  "citations": [
    {
      "doc_id": "invoice-001",
      "chunk_id": "invoice-001:chunk:2",
      "text": "Total: $4,250.00",
      "metadata": {"type": "invoice"}
    }
  ],
  "retrieval_mode": "hybrid",
  "used_rerank": true,
  "metadata": {}
}
```

### Fallback behavior

- If no documents are indexed: `"No indexed content is available to answer that question."`
- If retrieval returned results but the LLM cannot derive an answer from them: `"I cannot answer that from the indexed content because I could not find enough supporting context."`

---

## 14. Pipelines

Pipelines chain multiple steps into a single named request. Steps execute sequentially; each step's output feeds into the next.

### List available pipelines

```bash
curl http://localhost:8000/pipelines
```

### Run a pipeline

```bash
curl -X POST http://localhost:8000/pipelines/run \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_name": "ocr_extract_then_summary",
    "input": {
      "file_path": "/path/to/document.pdf",
      "provider": "openai",
      "model_name": "gpt-4o-mini",
      "api_key": "sk-..."
    }
  }'
```

### Built-in pipelines

| Pipeline | Steps | Required input fields |
|----------|-------|----------------------|
| `ocr_extract_only` | OCR extract → normalize | `file_path` |
| `ocr_extract_then_summary` | OCR extract → LLM summarization | `file_path`, `provider`, `model_name` |
| `ocr_extract_then_key_fields` | OCR extract → LLM key-field extraction | `file_path`, `provider`, `model_name` |

### Response shape

```json
{
  "pipeline_name": "ocr_extract_then_summary",
  "status": "completed",
  "steps": [
    {"step_name": "ocr_extract", "status": "completed", "output": {...}, "error": null},
    {"step_name": "ocr_postprocess", "status": "completed", "output": {...}, "error": null}
  ],
  "final_output": {...}
}
```

If any step fails, the pipeline stops and the failed step includes an `error` message.

---

## 15. Background Jobs

All workflows except `/llm/generate` can be submitted as background jobs.

### Submit a job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "retrieval.index_ocr",
    "input": {
      "doc_id": "report-q1",
      "file_path": "/path/to/report.pdf",
      "embedding_provider": "openai",
      "embedding_model_name": "text-embedding-3-small",
      "api_key": "sk-..."
    }
  }'
```

Returns HTTP 201 with the job record.

### Poll status

```bash
curl http://localhost:8000/jobs/{job_id}
```

| Status | Description |
|--------|-------------|
| `pending` | Queued, not yet picked up by the worker |
| `processing` | Worker is currently executing |
| `completed` | Finished — `result` field contains the output |
| `failed` | Error — `error` field contains the message |

### List all jobs

```bash
curl http://localhost:8000/jobs
```

### Job types

| Type | Equivalent endpoint |
|------|---------------------|
| `ocr.extract` | `POST /ocr/extract` |
| `ocr.postprocess` | `POST /ocr/postprocess` |
| `retrieval.index_ocr` | `POST /retrieval/index-ocr` |
| `retrieval.qa` | `POST /retrieval/qa` |
| `pipeline.run` | `POST /pipelines/run` |

**Security:** API keys in job inputs are stripped from stored records and held in a separate in-memory secret store. They are re-attached only during execution and cleared immediately after.

---

## 16. Evaluation & Stress Testing

### List benchmarks

```bash
curl http://localhost:8000/eval/benchmarks
```

### Available benchmark suites

| Suite | Description |
|-------|-------------|
| `ocr_smoke` | OCR extraction shape and normalization checks |
| `retrieval_smoke` | Dense and hybrid retrieval hit-presence checks |
| `rerank_smoke` | Reranking quality — relevant hit near top |
| `qa_smoke` | QA grounding, keyword, and citation checks |

### Run a benchmark

```bash
curl -X POST http://localhost:8000/eval/run/ocr_smoke \
  -H "Content-Type: application/json" \
  -d '{}'
```

Returns `benchmark_name`, `total_cases`, `passed_cases`, `failed_cases`, `average_latency_ms`, and per-case `results`.

### Stress test

```bash
curl -X POST http://localhost:8000/eval/stress \
  -H "Content-Type: application/json" \
  -d '{
    "test_type": "retrieval_search",
    "concurrency": 10,
    "iterations": 50,
    "payload": {
      "query": "contract expiry",
      "provider": "openai",
      "model_name": "text-embedding-3-small"
    }
  }'
```

| Test type | What it measures |
|-----------|------------------|
| `job_submit` | Job submission throughput |
| `retrieval_search` | Dense search latency under load |
| `document_qa` | Full QA pipeline latency under load |

Returns `successful_requests`, `failed_requests`, `average_latency_ms`, `p95_latency_ms`, and per-failure details.

---

## 17. Authentication

Authentication is **disabled by default**. All endpoints are open until you explicitly enable it.

### Enable authentication

Add to `.env`:

```env
DOCUMIND_AUTH_ENABLED=true
DOCUMIND_AUTH_SECRET_KEY=your-secret-key-at-least-32-characters
DOCUMIND_AUTH_ADMIN_USERNAME=admin
DOCUMIND_AUTH_ADMIN_PASSWORD=your-secure-password
```

### Obtain a token

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-secure-password"
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

Token payload includes `sub` (username), `role` (`"admin"`), and `exp` (expiration timestamp).

### Authenticate requests

```bash
curl http://localhost:8000/providers \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Public paths (no token required even when auth is enabled)

`/health`, `/health/live`, `/health/ready`, `/info`, `/auth/token`, `/docs`, `/docs/oauth2-redirect`, `/openapi.json`, `/redoc`

### Token errors

| Scenario | HTTP Status | Error message |
|----------|:-----------:|---------------|
| Missing token | 401 | `"Missing authentication token"` |
| Expired token | 401 | `"Token has expired"` |
| Invalid/malformed token | 401 | `"Invalid authentication token"` |
| Wrong credentials | 401 | `"Incorrect username or password"` |

> **Limitation:** All valid tokens share the same access level. Role-based authorization is not implemented.

---

## 18. Web UI

The React frontend at `http://localhost:5173` renders all forms dynamically from backend metadata — no hardcoded field configuration.

### Status indicators

The header shows a real-time server health strip:

- **Connected** (green) — backend responded successfully to the most recent health check (checked every 30 seconds).
- **Server unreachable** (red) — the last health check failed. Submissions will fail until connectivity is restored.

When the backend is configured with the in-memory vector store, a persistent banner reads:

> **Temporary storage:** Indexed documents are stored in memory and will be lost when the server restarts.

When authentication is disabled, a persistent banner reads:

> **Open access:** Authentication is disabled. Anyone who can reach this address can use the app.

### Workflow Presets

The main interface shows preset cards for common workflows:

| Preset | What it does |
|--------|-------------|
| **Extract Text** | Uploads a file → runs OCR → shows extracted text |
| **Extract & Summarize** | Uploads a file → runs OCR → generates a summary |
| **Extract Key Fields** | Uploads a file → runs OCR → extracts structured fields |
| **Index Document** | Uploads a file → runs OCR → chunks → embeds → stores in index |
| **Ask Your Documents** | Takes a text question → retrieves from index → reranks → generates an answer with citations |
| **Run Pipeline** | Selects and executes a named pipeline |

### UI features

- **Drag-and-drop file upload** in preset mode (accepted: `.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf`)
- **Provider/model selection** — dropdowns populated dynamically from the backend; falls back to a manual text input with contextual guidance when the model list cannot be loaded
- **BYOK API key field** — appears when a cloud provider is selected; includes a note indicating whether the server already has a configured key
- **Background job toggle** — submit any pipeline or retrieval workflow as a background job and poll for results inline
- **Smart result rendering** — OCR text as readable prose; QA answers with expandable source citations; key fields as a table; index results as a stat summary (document ID, sections indexed, OCR engine used)
- **Intermediate result disclosure** — in multi-step presets (e.g. Extract & Summarize), the intermediate OCR text is collapsed by default and can be expanded
- **Post-operation guidance** — after a successful Extract Text run, the UI suggests next steps (summarize, extract fields, or index); after a successful Index Document run, the UI points to Ask Your Documents
- **Indexed document management** — in the Ask Your Documents preset, the sidebar lists all indexed documents with a per-document **Remove** button (requires inline confirmation) and a **Clear all** action; each entry shows the chunk count and a metadata toggle
- **Raw JSON toggle** — every result card includes a collapsible "Show raw JSON" section for the full API response
- **Technical details disclosure** — background job status cards include a collapsible section showing the raw job ID and status code
- **Advanced API mode** — click "Switch to advanced mode" to access all endpoint parameters, request preview, and job submission JSON

---

## 19. Input Expectations

### File upload

| Constraint | Value |
|------------|-------|
| Accepted formats | `.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf` |
| Maximum size | 50 MB (configurable: `DOCUMIND_MAX_UPLOAD_SIZE_MB`) |
| Upload method | Multipart form data (`file` field) |
| File naming | Server renames to UUID + original extension |
| Auto-cleanup | After 60 minutes (configurable: `DOCUMIND_UPLOAD_TTL_MINUTES`) |

### API keys (BYOK)

- Cloud providers (OpenAI, Gemini, Anthropic) require either a server-side env variable or a per-request `api_key` field.
- Per-request `api_key` takes priority over the environment variable.
- Ollama does not require or accept an API key.

### Text inputs

- `prompt` (for `/llm/generate`): any non-empty string.
- `input_texts` (for `/embeddings/generate`): array of one or more non-empty strings.
- `query` (for search/QA): any non-empty string.
- `doc_id` (for indexing): any non-empty string you choose as a unique identifier.

---

## 20. Output & Result Behavior

### Common response headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request trace ID (enabled by default) |
| `X-Process-Time-MS` | Server-side request duration in milliseconds |

### Result rendering in the Web UI

| Result type | How it renders |
|-------------|----------------|
| OCR extraction | Full text as readable prose |
| Post-processing (`cleanup`, `summary`) | `output_text` as formatted prose |
| Post-processing (`extract_key_fields`) | Structured key-value table |
| Document QA | Answer text + expandable source citations |
| Embedding generation | Vector arrays (typically inspected via JSON toggle) |
| Background jobs | Status badge + result when completed |

All results include a "Show Raw JSON" toggle for the full API response.

---

## 21. Error States & Troubleshooting

### Standard error response format

All errors follow a consistent JSON shape:

```json
{
  "error": "Validation error",
  "detail": "body.model_name: Field required",
  "request_id": "5a95bf37d3f14a74b9bced2d2fb803b8"
}
```

### Common errors

| Symptom | HTTP Status | Likely Cause | Fix |
|---------|:-----------:|--------------|-----|
| `"Field required"` | 422 | Missing required request field | Check the parameter table for the endpoint |
| `"Unsupported file type"` | 400 | Upload of non-supported format | Use `.png`, `.jpg`, `.jpeg`, `.webp`, or `.pdf` |
| `"File too large"` | 400 | Upload exceeds size limit | Reduce file size or increase `DOCUMIND_MAX_UPLOAD_SIZE_MB` |
| `"Provider not found"` | 400 | Invalid provider name | Use `ollama`, `openai`, `gemini`, or `anthropic` |
| Connection refused on port 8000 | — | Backend not running | Run `uvicorn app.main:app --reload` |
| Connection refused on port 11434 | 502 | Ollama not running | Start Ollama (`ollama serve`) |
| `"Missing authentication token"` | 401 | Auth enabled but no Bearer token | Pass `Authorization: Bearer <token>` header |
| `"Token has expired"` | 401 | JWT past expiration time | Request a new token via `POST /auth/token` |
| Provider upstream error | 502 | Cloud provider returned an error | Check API key validity and provider status |
| Internal server error | 500 | Unhandled exception | Check server logs; `request_id` helps trace the issue |

### Health check failures

If `/health/ready` returns `"status": "degraded"`:
- Check the `checks` object to identify which component failed.
- `"redis": "error: ..."` → Redis is configured but not reachable. Verify `DOCUMIND_REDIS_URL`.
- `"milvus": "error: ..."` → Milvus is configured but not reachable. Verify `DOCUMIND_MILVUS_URI`.
- `"queue_initialized": "error"` → Worker failed to start. Check for startup errors in server logs.

---

## 22. Limitations & Important Notes

| Area | Limitation |
|------|-----------|
| **OCR** | Requires Ollama running locally. No cloud OCR provider is supported. |
| **OCR models** | Only `deepseek-ocr:3b` and `glm-ocr` are currently integrated. Custom OCR models require code changes. |
| **Embeddings** | Anthropic does not support embedding generation. Use Ollama, OpenAI, or Gemini for embeddings. |
| **Streaming** | No streaming or Server-Sent Events. All responses are returned as complete JSON. |
| **Job polling** | Background jobs are checked via polling (`GET /jobs/{id}`). There is no WebSocket or push notification. |
| **Vector store** | The default in-memory store loses all data on server restart. Use Milvus for persistence. |
| **Job queue** | The default in-memory queue loses all pending/running jobs on server restart. Use Redis for durability. |
| **Auth** | Single admin user only. No user registration, no role-based access control. All tokens have identical privileges. |
| **Auth secrets** | Default `auth_secret_key` and `auth_admin_password` are insecure dev defaults. **Change them before any non-local deployment.** |
| **Concurrency** | The in-memory job worker processes one job at a time. Throughput scales with Redis + multiple worker processes. |
| **File cleanup** | Uploaded files are auto-deleted after the configured TTL. If the server restarts, orphaned files may remain in the upload directory until the next cleanup cycle. |
| **CORS** | No origins are allowed by default. Set `DOCUMIND_CORS_ALLOW_ORIGINS` for cross-origin frontend access. |

---

## 23. Configuration Reference

All environment variables use the `DOCUMIND_` prefix. Provider key variables (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) are also accepted without the prefix.

Copy `.env.example` to `.env` and edit as needed. See individual sections above for context on each setting.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_APP_NAME` | `DocuMind` | Application name (shown in `/info`) |
| `DOCUMIND_APP_ENV` | `dev` | Runtime environment label |
| `DOCUMIND_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DOCUMIND_DEBUG` | `false` | Enable debug mode |
| `DOCUMIND_CORS_ALLOW_ORIGINS` | `[]` | JSON array or comma-separated list of allowed CORS origins |
| `DOCUMIND_API_REQUEST_TIMEOUT_SECONDS` | `60` | API request timeout |
| `DOCUMIND_ENABLE_REQUEST_ID` | `true` | Attach `X-Request-ID` header to all responses |
| `DOCUMIND_HTTP_TIMEOUT_SECONDS` | `10` | General outbound HTTP timeout |

### Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `DOCUMIND_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `DOCUMIND_OLLAMA_HTTP_TIMEOUT_SECONDS` | `120` | Ollama HTTP request timeout |
| `DOCUMIND_OLLAMA_KEEP_ALIVE` | `5m` | Ollama model keep-alive duration |
| `DOCUMIND_OLLAMA_DEEPSEEK_OCR_MODEL` | `deepseek-ocr:3b` | DeepSeek-OCR model tag in Ollama |
| `DOCUMIND_OLLAMA_GLM_OCR_MODEL` | `glm-ocr` | GLM-OCR model tag in Ollama |
| `DOCUMIND_LLM_DEFAULT_MAX_OUTPUT_TOKENS` | `1024` | Default max output tokens for LLM generation |

### Upload

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_UPLOAD_DIR` | System temp | Directory for uploaded files (empty = OS temp directory) |
| `DOCUMIND_MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size in MB |
| `DOCUMIND_UPLOAD_TTL_MINUTES` | `60` | Auto-cleanup TTL for uploaded files |

### Vector Store

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_VECTOR_STORE_BACKEND` | `memory` | `memory` (in-process) or `milvus` (persistent) |
| `DOCUMIND_MILVUS_URI` | `http://localhost:19530` | Milvus connection URI |
| `DOCUMIND_MILVUS_COLLECTION_NAME` | `documind_chunks` | Milvus collection name |
| `DOCUMIND_MILVUS_VECTOR_DIM` | `768` | Embedding vector dimension |
| `DOCUMIND_MILVUS_TOKEN` | — | Milvus Cloud authentication token |

### Job Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_JOB_QUEUE_BACKEND` | `memory` | `memory` (in-process) or `redis` (persistent) |
| `DOCUMIND_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `DOCUMIND_WORKER_ENABLED` | `true` | Start the background job worker on server boot |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_AUTH_ENABLED` | `false` | Enable JWT authentication middleware |
| `DOCUMIND_AUTH_SECRET_KEY` | `change-me-in-production` | JWT signing secret — **change for any non-local use** |
| `DOCUMIND_AUTH_ALGORITHM` | `HS256` | JWT signing algorithm |
| `DOCUMIND_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime in minutes |
| `DOCUMIND_AUTH_ADMIN_USERNAME` | `admin` | Admin username |
| `DOCUMIND_AUTH_ADMIN_PASSWORD` | `admin` | Admin password — **change for any non-local use** |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL (set in `ui/.env`) |
