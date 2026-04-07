# 📖 DocuMind User Guide

A practical, feature-by-feature guide to using DocuMind. Every example uses
`curl` against a locally-running server. The interactive Swagger UI at
`http://127.0.0.1:8000/docs` lets you explore and test every endpoint in the
browser without writing any code.

---

## Table of Contents

1. [Starting the App](#1-starting-the-app)
2. [Health & Status Checks](#2-health--status-checks)
3. [Configuring Providers](#3-configuring-providers)
4. [OCR — Extract Text From Documents](#4-ocr--extract-text-from-documents)
5. [OCR Post-Processing](#5-ocr-post-processing)
6. [LLM Text Generation](#6-llm-text-generation)
7. [Embedding Generation](#7-embedding-generation)
8. [Retrieval — Indexing Documents](#8-retrieval--indexing-documents)
9. [Retrieval — Searching](#9-retrieval--searching)
10. [Document QA](#10-document-qa)
11. [Named Pipelines](#11-named-pipelines)
12. [Background Jobs](#12-background-jobs)
13. [Evaluation & Stress Testing](#13-evaluation--stress-testing)
14. [Authentication (Optional)](#14-authentication-optional)
15. [Using the React UI](#15-using-the-react-ui)
16. [Environment Variables Reference](#16-environment-variables-reference)

---

## 1. Starting the App

### Backend

```bash
# Install dependencies (first time only)
pip install -e ".[dev]"

# Copy the environment template
cp .env.example .env   # macOS / Linux
Copy-Item .env.example .env  # Windows PowerShell

# Start the API server
uvicorn app.main:app --reload
```

The API will be available at **`http://127.0.0.1:8000`**.  
Swagger UI: **`http://127.0.0.1:8000/docs`**

### Frontend (optional)

```bash
cd ui
npm install
npm run dev
```

UI available at **`http://localhost:5173`**.  
Set `VITE_API_BASE_URL` in a `.env` file inside `ui/` if the backend is on a
different host or port.

### Ollama (for local models)

```bash
ollama pull deepseek-ocr:3b   # general-purpose OCR
ollama pull glm-ocr            # structured-output OCR
```

---

## 2. Health & Status Checks

Verify the server is running before sending real requests.

```bash
# Liveness — process running?
curl http://127.0.0.1:8000/health/live

# Readiness — queue and model manager accessible?
curl http://127.0.0.1:8000/health/ready

# App metadata
curl http://127.0.0.1:8000/info
```

**Example response (`/health/live`)**

```json
{ "status": "ok" }
```

**Example response (`/health/ready`)**

```json
{
  "status": "ok",
  "checks": {
    "queue_initialized": true,
    "model_manager_accessible": true
  }
}
```

---

## 3. Configuring Providers

List all supported providers and see which ones require an API key:

```bash
curl http://127.0.0.1:8000/providers
```

List models available from a specific provider (BYOK cloud providers accept an
optional `api_key` in the body):

```bash
# Ollama — no key needed
curl -X POST http://127.0.0.1:8000/providers/ollama/models \
  -H "Content-Type: application/json" \
  -d '{}'

# OpenAI — pass your key
curl -X POST http://127.0.0.1:8000/providers/openai/models \
  -H "Content-Type: application/json" \
  -d '{ "api_key": "sk-..." }'
```

### Ollama Runtime

Activate a model before using it with Ollama-backed operations:

```bash
# Check current runtime state
curl http://127.0.0.1:8000/runtime/status

# Activate a model
curl -X POST http://127.0.0.1:8000/runtime/activate \
  -H "Content-Type: application/json" \
  -d '{ "provider": "ollama", "model_name": "llama3" }'

# Deactivate
curl -X POST http://127.0.0.1:8000/runtime/deactivate \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 4. OCR — Extract Text From Documents

Extract text from a single image or multi-page PDF.

### Supported file types

| Type | Extensions |
|------|-----------|
| Images | `.png`, `.jpg`, `.jpeg`, `.webp` |
| PDF | `.pdf` (split into per-page images automatically) |

### Basic extraction (auto-route engine)

```bash
curl -X POST http://127.0.0.1:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/absolute/path/to/document.pdf",
    "prefer_structure": true
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_path` | string | ✅ | Absolute path to the file on the server |
| `engine` | string | — | `"deepseek-ocr"` or `"glm-ocr"`. Omit for auto-routing |
| `prefer_structure` | bool | — | Request structured output (headers, tables). Default `false` |

### Force a specific engine

```bash
curl -X POST http://127.0.0.1:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/invoice.png",
    "engine": "glm-ocr",
    "prefer_structure": true
  }'
```

### Check which engine will be picked (without running OCR)

```bash
curl -X POST http://127.0.0.1:8000/ocr/route \
  -H "Content-Type: application/json" \
  -d '{ "file_path": "/path/to/document.png" }'
```

### Response shape

```json
{
  "engine": "glm-ocr",
  "text": "...merged plain text...",
  "normalized_text": "...cleaned text...",
  "normalization": {
    "removed_blank_lines": 4,
    "collapsed_whitespace": true,
    "merged_broken_lines": true,
    "cleaned_hyphenation": false
  },
  "structured": { ... },
  "layout": { "pages": 3, "structure": true },
  "tables": [],
  "confidence": 0.0,
  "metadata": { "model": "glm-ocr" },
  "pages": [
    { "page": 1, "text": "...", "confidence": 0.0, "metadata": {} },
    { "page": 2, "text": "...", "confidence": 0.0, "metadata": {} }
  ]
}
```

> **PDF tip:** The `pages` array contains per-page OCR results. `text` is the
> full merged text across all pages.

---

## 5. OCR Post-Processing

Run an LLM over extracted OCR text to clean it up, summarize it, or pull
structured fields.

```bash
curl -X POST http://127.0.0.1:8000/ocr/postprocess \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summary",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "ocr_result": { ...paste full OCR response here... }
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ocr_result` | object | ✅ | Full OCR response from `/ocr/extract` |
| `task` | string | ✅ | `"cleanup"`, `"summary"`, or `"extract_key_fields"` |
| `provider` | string | ✅ | LLM provider to use |
| `model_name` | string | ✅ | Model name for the provider |
| `api_key` | string | — | BYOK API key for cloud providers |
| `temperature` | float | — | Sampling temperature (≥ 0) |
| `max_output_tokens` | int | — | Maximum tokens in the LLM response |

### Task types

| Task | What it does |
|------|-------------|
| `cleanup` | Fix OCR artefacts, normalise whitespace and word boundaries |
| `summary` | Produce a concise summary of the document content |
| `extract_key_fields` | Extract structured key-value pairs from the text |

### Response shape

```json
{
  "task": "summary",
  "provider": "openai",
  "model_name": "gpt-4o-mini",
  "output_text": "This invoice is for...",
  "usage": { "input_tokens": 312, "output_tokens": 80 },
  "metadata": {}
}
```

---

## 6. LLM Text Generation

Call any supported LLM provider directly without going through OCR.

```bash
curl -X POST http://127.0.0.1:8000/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "model_name": "llama3",
    "prompt": "Explain retrieval-augmented generation in two sentences.",
    "temperature": 0.3
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | ✅ | `"ollama"`, `"openai"`, `"gemini"`, or `"anthropic"` |
| `model_name` | string | ✅ | Model to call |
| `prompt` | string | ✅ | The prompt to send |
| `api_key` | string | — | BYOK for cloud providers |
| `temperature` | float | — | Sampling temperature |
| `max_output_tokens` | int | — | Token budget for the response |

> **Note:** `llm/generate` is direct-only; it cannot be submitted as a
> background job.

---

## 7. Embedding Generation

Generate vector embeddings for a text string.

```bash
curl -X POST http://127.0.0.1:8000/embeddings/generate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "text": "What are the payment terms in this contract?",
    "api_key": "sk-..."
  }'
```

Returns a float array you can use with external tools or inspect for debugging.

---

## 8. Retrieval — Indexing Documents

Before you can search or ask questions, documents must be indexed.

### Option A — Index plain text

Provide text you already have without running OCR:

```bash
curl -X POST http://127.0.0.1:8000/retrieval/index \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "contract-2024",
    "text": "This agreement is entered into on January 1 2024...",
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "metadata": { "source": "contracts", "year": 2024 }
  }'
```

### Option B — Index from a file (OCR + embed in one call)

```bash
curl -X POST http://127.0.0.1:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "invoice-001",
    "file_path": "/path/to/invoice.pdf",
    "embedding_provider": "openai",
    "embedding_model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "ocr_engine": "glm-ocr",
    "prefer_structure": true,
    "metadata": { "type": "invoice", "vendor": "Acme" }
  }'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `doc_id` | string | ✅ | Unique document identifier |
| `file_path` | string | ✅ | Absolute path to the file |
| `embedding_provider` | string | ✅ | Provider for embeddings |
| `embedding_model_name` | string | ✅ | Embedding model |
| `api_key` | string | — | BYOK API key |
| `ocr_engine` | string | — | `"deepseek-ocr"` or `"glm-ocr"` (auto if omitted) |
| `prefer_structure` | bool | — | Request structured OCR output |
| `metadata` | object | — | Arbitrary metadata attached to all chunks |

### List indexed documents

```bash
curl http://127.0.0.1:8000/retrieval/documents
```

### Clear the index

```bash
curl -X DELETE http://127.0.0.1:8000/retrieval/documents
```

---

## 9. Retrieval — Searching

### Dense vector search

```bash
curl -X POST http://127.0.0.1:8000/retrieval/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment terms",
    "provider": "openai",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "top_k": 5
  }'
```

### Hybrid search (dense + BM25 sparse)

```bash
curl -X POST http://127.0.0.1:8000/retrieval/hybrid-search \
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

| Field | Description |
|-------|-------------|
| `dense_weight` | Weight for vector similarity results (0–1, default 0.5) |
| `sparse_weight` | Weight for BM25 keyword results (0–1, default 0.5) |

### Rerank retrieved results

Pass results from a previous search through LLM-based reranking:

```bash
curl -X POST http://127.0.0.1:8000/retrieval/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "payment terms",
    "hits": [ ...array of search result objects... ],
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "top_k": 3
  }'
```

---

## 10. Document QA

Ask a question grounded in indexed documents. Retrieval, optional reranking,
and LLM answer generation all happen in a single call.

```bash
curl -X POST http://127.0.0.1:8000/retrieval/qa \
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

| Field | Default | Description |
|-------|---------|-------------|
| `query` | — | The question to answer |
| `provider` / `model_name` | — | LLM provider and model for answer generation |
| `retrieval_mode` | `"hybrid"` | `"dense"` or `"hybrid"` |
| `top_k` | `5` | Candidate chunks to retrieve |
| `use_rerank` | `true` | Apply LLM reranking before answering |
| `rerank_top_k` | `5` | Chunks passed to the LLM after reranking |

### Response shape

```json
{
  "query": "What is the total on invoice 001?",
  "answer": "The total amount is $4,250.00.",
  "citations": [
    {
      "doc_id": "invoice-001",
      "chunk_id": "invoice-001:c2",
      "text": "Total: $4,250.00",
      "metadata": { "type": "invoice" }
    }
  ],
  "retrieval_mode": "hybrid",
  "used_rerank": true,
  "metadata": {}
}
```

---

## 11. Named Pipelines

Pipelines chain multiple steps together under a single named request.

### List available pipelines

```bash
curl http://127.0.0.1:8000/pipelines
```

### Run a pipeline

```bash
curl -X POST http://127.0.0.1:8000/pipelines/run \
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

| Pipeline name | Steps |
|--------------|-------|
| `ocr_extract_only` | OCR extract → normalize |
| `ocr_extract_then_summary` | OCR extract → summarize with LLM |
| `ocr_extract_then_key_fields` | OCR extract → extract key fields with LLM |

---

## 12. Background Jobs

Every workflow (except `llm/generate`) can be offloaded to a background job so
you do not have to wait for the response inline.

### Submit a job

```bash
curl -X POST http://127.0.0.1:8000/jobs \
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

**Response**

```json
{
  "job_id": "a3f7b812c90d4e1f",
  "type": "retrieval.index_ocr",
  "status": "pending",
  "input": { "doc_id": "report-q1", ... }
}
```

### Poll job status

```bash
curl http://127.0.0.1:8000/jobs/a3f7b812c90d4e1f
```

| Status | Meaning |
|--------|---------|
| `pending` | Queued, not yet picked up |
| `processing` | Worker is executing the job |
| `completed` | Finished — `result` field contains output |
| `failed` | Error — `error` field contains the message |

### List all jobs

```bash
curl http://127.0.0.1:8000/jobs
```

### Available job types

| Job type | Equivalent direct endpoint |
|----------|---------------------------|
| `ocr.extract` | `POST /ocr/extract` |
| `ocr.postprocess` | `POST /ocr/postprocess` |
| `retrieval.index_ocr` | `POST /retrieval/index-ocr` |
| `retrieval.qa` | `POST /retrieval/qa` |
| `pipeline.run` | `POST /pipelines/run` |

> **BYOK note:** `api_key` values are stripped from stored job records and held
> in a separate in-memory secret store. They are re-attached only during
> execution and cleared immediately after.

---

## 13. Evaluation & Stress Testing

### List benchmarks

```bash
curl http://127.0.0.1:8000/eval/benchmarks
```

### Run a benchmark suite

```bash
curl -X POST http://127.0.0.1:8000/eval/run/ocr_basic \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Response includes:** `total_cases`, `passed_cases`, `average_latency_ms`, and
per-case results with metrics and any errors.

### Stress test

Measure throughput and latency under concurrent load:

```bash
curl -X POST http://127.0.0.1:8000/eval/stress \
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

| `test_type` | What it tests |
|-------------|--------------|
| `job_submit` | Background job submission throughput |
| `retrieval_search` | Dense retrieval search latency |
| `document_qa` | Full QA pipeline latency |

**Response includes:** `successful_requests`, `failed_requests`,
`average_latency_ms`, `p95_latency_ms`.

---

## 14. Authentication (Optional)

Authentication is **disabled by default**. Enable it by setting the following
environment variables (or in your `.env` file):

```env
DOCUMIND_AUTH_ENABLED=true
DOCUMIND_AUTH_SECRET_KEY=your-32-char-or-longer-secret
DOCUMIND_AUTH_ADMIN_USERNAME=admin
DOCUMIND_AUTH_ADMIN_PASSWORD=your-secure-password
DOCUMIND_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Get a token

```bash
curl -X POST http://127.0.0.1:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your-secure-password"
```

**Response**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Use the token

Pass the token via the `Authorization` header on all subsequent requests:

```bash
curl http://127.0.0.1:8000/providers \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Public paths (always accessible without a token)

`/health/live`, `/health/ready`, `/health`, `/info`, `/auth/token`, `/docs`,
`/openapi.json`, `/redoc`

> **Current limitation:** Token validation confirms identity but there is no
> role-based authorization. All valid tokens have the same access level.

---

## 15. Using the React UI

The frontend at `http://localhost:5173` builds its forms and menus dynamically
from the backend API — no hardcoded configuration is needed.

### What the UI provides

- **OCR** — Upload or point to a file, choose an engine, run extraction and
  view structured results.
- **OCR Post-Process** — Paste or forward OCR output and run cleanup, summary,
  or key-field extraction.
- **LLM Generate** — Free-form text generation with any provider.
- **Retrieval** — Index documents, run search, hybrid search, or QA queries.
- **Pipelines** — Browse and execute named pipelines with a single form.
- **Jobs** — Submit any workflow as a background job, then poll for results.
- **Evaluation** — Trigger benchmark suites and stress tests, view metrics.

### Workflow presets

The UI includes presets that chain multiple backend calls automatically:

| Preset | Steps automated |
|--------|----------------|
| OCR + Summary | OCR extract → OCR postprocess (summary) |
| OCR + Key Fields | OCR extract → OCR postprocess (extract_key_fields) |
| Index & Ask | Index document via OCR → document QA |

### Provider / model selection

Every form that calls an LLM includes provider and model dropdowns populated
dynamically from `GET /providers` and `POST /providers/{provider}/models`.

---

## 16. Environment Variables Reference

All variables use the `DOCUMIND_` prefix. Bare names like `OPENAI_API_KEY` are
also resolved automatically.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_APP_ENV` | `dev` | Runtime environment label |
| `DOCUMIND_LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DOCUMIND_DEBUG` | `false` | Enable debug mode |
| `DOCUMIND_CORS_ALLOW_ORIGINS` | *(empty)* | Comma-separated allowed CORS origins |

### Providers

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (also `DOCUMIND_OPENAI_API_KEY`) |
| `GEMINI_API_KEY` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `DOCUMIND_OLLAMA_BASE_URL` | Ollama server URL (default `http://localhost:11434`) |
| `DOCUMIND_OLLAMA_HTTP_TIMEOUT_SECONDS` | HTTP timeout for Ollama calls (default `120`) |
| `DOCUMIND_OLLAMA_DEEPSEEK_OCR_MODEL` | Model name for DeepSeek-OCR (default `deepseek-ocr:3b`) |
| `DOCUMIND_OLLAMA_GLM_OCR_MODEL` | Model name for GLM-OCR (default `glm-ocr`) |

### Vector Store

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_VECTOR_STORE_BACKEND` | `memory` | `memory` or `milvus` |
| `DOCUMIND_MILVUS_URI` | `http://localhost:19530` | Milvus connection URI |
| `DOCUMIND_MILVUS_COLLECTION_NAME` | `documind_chunks` | Milvus collection name |
| `DOCUMIND_MILVUS_VECTOR_DIM` | `768` | Embedding vector dimension |
| `DOCUMIND_MILVUS_TOKEN` | *(empty)* | Auth token for Milvus Cloud |

### Job Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_JOB_QUEUE_BACKEND` | `memory` | `memory` or `redis` |
| `DOCUMIND_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_AUTH_ENABLED` | `false` | Enable JWT authentication middleware |
| `DOCUMIND_AUTH_SECRET_KEY` | *(dev default)* | **Change this in production.** JWT signing secret |
| `DOCUMIND_AUTH_ALGORITHM` | `HS256` | JWT signing algorithm |
| `DOCUMIND_AUTH_ADMIN_USERNAME` | `admin` | Admin login username |
| `DOCUMIND_AUTH_ADMIN_PASSWORD` | `admin` | **Change this in production.** Admin password |
| `DOCUMIND_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime in minutes |

---

## Quick-Start Cheatsheet

```bash
# 1. Start server
uvicorn app.main:app --reload

# 2. Confirm it's up
curl http://127.0.0.1:8000/health/live

# 3. Extract text from a PDF
curl -X POST http://127.0.0.1:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/path/to/doc.pdf","prefer_structure":true}'

# 4. Index the document for QA
curl -X POST http://127.0.0.1:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"doc1","file_path":"/path/to/doc.pdf",
       "embedding_provider":"openai","embedding_model_name":"text-embedding-3-small",
       "api_key":"sk-..."}'

# 5. Ask a question
curl -X POST http://127.0.0.1:8000/retrieval/qa \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the key terms?","provider":"openai",
       "model_name":"gpt-4o-mini","api_key":"sk-...",
       "retrieval_mode":"hybrid","use_rerank":true}'
```
