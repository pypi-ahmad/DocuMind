# Architecture

## System Overview

DocuMind is a single-process FastAPI application that exposes REST endpoints for
document OCR, LLM post-processing, retrieval-augmented QA, evaluation, and a
browser-based UI. By default everything runs in one Python process with in-memory
stores — no external databases, brokers, or containers are required.

Optionally, the vector store can be switched to **Milvus** and the job queue to
**Redis** for persistent, multi-node operation.  A standalone worker CLI
(`python -m app.workers.cli`) allows job execution to run in separate processes.
JWT-based authentication can be enabled via configuration.

```
┌─────────────┐        ┌──────────────────────────────────────────────────┐
│  React UI   │  HTTP  │  FastAPI process                                 │
│  (Vite)     │ ────── │                                                  │
└─────────────┘        │  ┌────────────────────────────────────────────┐  │
                       │  │  Routes (app/api/routes/)                  │  │
                       │  │   system · ocr · llm · retrieval ·         │  │
                       │  │   pipelines · jobs · providers · eval · ui │  │
                       │  └──────────────┬─────────────────────────────┘  │
                       │                 │                                 │
                       │  ┌──────────────▼─────────────────────────────┐  │
                       │  │  Services (app/services/)                  │  │
                       │  │   ocr_postprocess · indexing · chunking ·  │  │
                       │  │   embedding_service · retrieval_store ·    │  │
                       │  │   hybrid_retrieval · sparse_retrieval ·    │  │
                       │  │   reranker · document_qa ·                 │  │
                       │  │   pipeline_runner                          │  │
                       │  └──────────────┬─────────────────────────────┘  │
                       │                 │                                 │
                       │  ┌──────────────▼──────────┐  ┌───────────────┐  │
                       │  │  Providers (app/providers) │  OCR engines  │  │
                       │  │  ollama · openai ·       │  │  (app/ocr/)  │  │
                       │  │  gemini · anthropic      │  │  deepseek ·  │  │
                       │  └─────────────────────────┘  │  glm          │  │
                       │                                └───────────────┘  │
                       │  ┌───────────────────────────────────────────┐    │
                       │  │  Workers (app/workers/)                   │    │
                       │  │   queue.py — facade (memory / Redis)      │    │
                       │  │   worker.py — background job processor    │    │
                       │  │   redis_queue.py — Redis-backed queue     │    │
                       │  │   cli.py — standalone worker process      │    │
                       │  └───────────────────────────────────────────┘    │
                       │  ┌───────────────────────────────────────────┐    │
                       │  │  Eval (app/eval/)                         │    │
                       │  │   benchmarks · evaluator · metrics ·      │    │
                       │  │   stress                                  │    │
                       │  └───────────────────────────────────────────┘    │
                       └──────────────────────────────────────────────────┘

                       Optional external services (when configured):
                       ┌──────────────┐   ┌──────────────┐
                       │  Milvus      │   │  Redis       │
                       │  (vectors)   │   │  (job queue) │
                       └──────────────┘   └──────────────┘
```

## Major Modules

### `app/api/routes/`

Each file maps to an endpoint group. Routes validate inputs via Pydantic schemas
(`app/schemas/`) and delegate to services or providers.

### `app/providers/`

LLM provider adapters behind `BaseProvider` (ABC). Each provider normalizes
responses into the same `text`, `usage`, `metadata` shape. `registry.py` looks up
providers by name.

### `app/ocr/`

OCR engine adapters behind `BaseOCREngine` (ABC). `router.py` selects an engine
automatically or uses the caller's override. `pdf.py` splits multi-page PDFs into
per-page images via PyMuPDF. `normalize.py` and `structure.py` post-process raw
OCR output into a consistent format.

### `app/services/`

Domain logic that glues providers, OCR, and retrieval together:

| Service | Responsibility |
|---------|---------------|
| `ocr_postprocess` | Send OCR output to an LLM for summarization or key-field extraction |
| `indexing` | Orchestrate extract → chunk → embed → store |
| `chunking` | Split text into overlapping chunks |
| `embedding_service` | Generate vector embeddings via a provider |
| `retrieval_store` | Document store facade — in-memory or Milvus backend |
| `milvus_store` | Milvus-backed vector store implementation |
| `sparse_retrieval` | BM25-based sparse search |
| `hybrid_retrieval` | Merge dense and sparse results |
| `reranker` | Cross-encoder–style reranking of search results |
| `document_qa` | Retrieval-augmented question answering |
| `pipeline_runner` | Execute named multi-step pipeline definitions |

### `app/workers/`

Job queue facade (`queue.py`) dispatches to an in-memory `asyncio.Queue` or a
Redis-backed queue (`redis_queue.py`) based on `DOCUMIND_JOB_QUEUE_BACKEND`.
A background task (`worker.py`) processes jobs in the main FastAPI process.
For multi-node deployments, `cli.py` provides a standalone worker process that
dequeues jobs from Redis independently.

Jobs are created via `POST /jobs` and polled via `GET /jobs/{job_id}`. API keys
in job inputs are stripped from the stored job record and held separately until
execution, then cleared.

### `app/eval/`

Benchmark definitions, an evaluation runner, scoring metrics, and a stress test
driver, all exposed through `/eval/*` endpoints.

### `app/core/`

Cross-cutting concerns:

- `settings.py` — pydantic-settings with `.env` support and alias-based key resolution.
- `auth.py` — JWT authentication: token creation, validation, login endpoint, `get_current_user` dependency.
- `pipelines.py` — static pipeline definitions (steps, required fields).
- `model_manager.py` — Ollama model pull/activation lifecycle.
- `errors.py` — global exception handlers.
- `middleware.py` — request ID injection, timing headers, and optional auth enforcement.
- `logging.py` — structured logging configuration.

---

## Request Flow — Direct Mode

```
Client ─► Route handler
               │
               ├─ validate request (Pydantic schema)
               ├─ call service / provider
               └─ return JSON response
```

## Request Flow — Job Mode

```
Client ─► POST /jobs
               │
               ├─ create_job() — store in _jobs dict, enqueue job_id
               └─ return JobResponse (status: pending)

Worker loop:
    dequeue job_id ─► get_job_input() (re-attach secrets)
                          │
                          ├─ dispatch by job type
                          ├─ update_job(status: completed, result: …)
                          └─ clear_job_secrets()

Client ─► GET /jobs/{job_id} ─► return current JobResponse
```

## OCR Flow

```
POST /ocr/extract
    │
    ├─ router.py selects engine (or uses caller override)
    ├─ engine.extract(file_path)
    │      ├─ if PDF → pdf.py splits pages, OCR each, merge
    │      └─ if image → encode + single Ollama call
    ├─ normalize.py → consistent text format
    ├─ structure.py → structured output (optional)
    └─ return OCR result (with per-page data for PDFs)

POST /ocr/postprocess
    │
    ├─ receive OCR result + task (summary | extract_key_fields)
    ├─ build LLM prompt from OCR text
    ├─ call provider.generate()
    └─ return post-processed result
```

## Retrieval / QA Flow

```
POST /retrieval/index-ocr
    │
    ├─ OCR extract (reuses extract flow)
    ├─ chunking.split()
    ├─ embedding_service.embed(chunks)
    └─ retrieval_store.add_documents()

POST /retrieval/qa
    │
    ├─ embed query
    ├─ hybrid_retrieval.search() (dense + BM25)
    ├─ reranker.rerank() (optional)
    ├─ document_qa.answer() — prompt LLM with context
    └─ return answer + source references
```

## UI ↔ Backend Interaction

The React frontend discovers all available capabilities at startup:

1. `GET /ui/config` — providers, OCR engines, retrieval modes, route map.
2. `GET /ui/forms` — field-level metadata for each action form.

The UI builds forms dynamically from this metadata. It never hard-codes backend
routes or field definitions. Workflow presets are a browser-only orchestration
layer that calls existing backend endpoints in sequence.
