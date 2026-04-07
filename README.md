<h1 align="center">DocuMind</h1>

<p align="center">
  <strong>OCR-first document intelligence — extract, structure, index, and query documents through a unified API.</strong>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img alt="React 19" src="https://img.shields.io/badge/React_19-20232A?style=flat-square&logo=react&logoColor=61DAFB" />
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-16A34A?style=flat-square" />
</p>

---

DocuMind treats OCR text extraction as the primary contract rather than a hidden preprocessing step. Upload a document, extract its content through local OCR models, optionally post-process it with any supported LLM, index it into a vector store, and ask questions grounded in your documents — all through a single FastAPI backend and a React frontend, runnable locally with zero external infrastructure required.

## What It Does

- **Extracts text** from images and multi-page PDFs using local Ollama-hosted OCR models (DeepSeek-OCR, GLM-OCR).
- **Post-processes** OCR output with LLMs — cleanup, summarization, or structured key-field extraction.
- **Indexes documents** by chunking text, generating embeddings, and storing vectors for retrieval.
- **Searches** via dense vector similarity, BM25 keyword matching, or a weighted hybrid of both.
- **Answers questions** through retrieval-augmented generation with LLM-based reranking and source citations.
- **Runs as background jobs** — any workflow (except direct LLM generation) can be submitted asynchronously and polled.

## Why It Exists

Most document processing tools bury OCR behind opaque pipelines. DocuMind surfaces every step — extraction, normalization, structuring, embedding, retrieval, answer generation — as explicit, testable, and independently callable API endpoints. Each step produces inspectable output. Each step can be swapped (different OCR engine, different LLM provider, different vector store) without rewriting the pipeline.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12+, FastAPI, Pydantic, uvicorn |
| Frontend | React 19, TypeScript, Vite 7 |
| OCR | Ollama (DeepSeek-OCR, GLM-OCR), PyMuPDF for PDF rendering |
| LLM Providers | Ollama (local), OpenAI, Google Gemini, Anthropic |
| Retrieval | NumPy cosine similarity, rank-bm25 for sparse, LLM-based reranking |
| Vector Store | In-memory (default), Milvus (optional) |
| Job Queue | In-memory (default), Redis (optional) |
| Auth | JWT via PyJWT (optional, disabled by default) |
| HTTP | httpx for provider calls |

## Features

| Feature | Details |
|---------|---------|
| **OCR Extraction** | `.png`, `.jpg`, `.jpeg`, `.webp`, `.pdf` — multi-page PDFs processed per-page |
| **Post-Processing** | `cleanup`, `summary`, `extract_key_fields` tasks via any supported LLM |
| **Hybrid Retrieval** | Dense (embedding similarity) + sparse (BM25) with configurable weights |
| **LLM-Based Reranking** | Re-scores retrieved chunks using provider-agnostic LLM relevance judgment |
| **Document QA** | Retrieve → rerank → answer with citations. Grounded responses only |
| **Multi-Provider** | Ollama, OpenAI, Gemini, Anthropic — same interface, per-request provider selection |
| **BYOK** | Bring-your-own-key on every request. Keys are never persisted to disk |
| **Background Jobs** | Async submit + poll. In-memory or Redis-backed queue |
| **Pipelines** | Named multi-step workflows: `ocr_extract_only`, `ocr_extract_then_summary`, `ocr_extract_then_key_fields` |
| **Evaluation** | Built-in benchmark suites (`ocr_smoke`, `retrieval_smoke`, `rerank_smoke`, `qa_smoke`) and stress tests |
| **Optional Auth** | JWT middleware, disabled by default. Single admin user, configurable credentials |
| **Schema-Driven UI** | Frontend forms generated from backend metadata — no manual field sync |

## Architecture

```
React UI (Vite)
    │
    ▼
FastAPI Backend
    ├── /ocr/*          OCR extraction, routing, post-processing
    ├── /llm/*          Direct text generation
    ├── /embeddings/*   Vector embedding generation
    ├── /retrieval/*    Indexing, search, hybrid search, reranking, QA
    ├── /pipelines/*    Named multi-step workflows
    ├── /jobs/*         Background job submission and polling
    ├── /providers/*    Provider discovery and model listing
    ├── /runtime/*      Ollama model activation/deactivation
    ├── /eval/*         Benchmarks and stress tests
    ├── /auth/token     JWT token endpoint (when enabled)
    ├── /health/*       Liveness and readiness probes
    └── /ui/*           Frontend config and form descriptors
            │
            ▼
    Ollama / OpenAI / Gemini / Anthropic
```

**Local-first by default.** No database, message broker, or cloud account required to start. Milvus, Redis, and JWT auth are opt-in.

## Project Structure

```
app/
  main.py          Application entry point (FastAPI, lifespan, middleware, routers)
  api/
    routes/        Route handlers for each endpoint group
    router.py      System routes (health, info)
  core/            Settings, auth, errors, middleware, logging, secrets, model manager, pipelines
  eval/            Benchmark definitions, stress tests, evaluator
  ocr/             OCR engine base, DeepSeek, GLM, PDF splitting, normalization, structuring
  providers/       Provider adapters (Ollama, OpenAI, Gemini, Anthropic) and registry
  schemas/         Pydantic request/response models
  services/        Chunking, embedding, indexing, retrieval, reranking, QA, post-processing
  workers/         Job queue (memory/Redis), background worker, standalone CLI
docs/
  usage.md         Complete usage guide with curl examples and configuration reference
  development.md   Extension points for providers, OCR engines, pipelines
tests/             16 test modules covering OCR, providers, retrieval, jobs, eval, upload, schemas
ui/                React 19 + TypeScript + Vite frontend
```

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.12+** | Backend runtime |
| **Node.js 18+** | Frontend only — skip if using API directly |
| **Ollama** | Required for local OCR and local LLM inference. Optional if using only cloud providers |

## Installation

```bash
# Clone
git clone https://github.com/pypi-ahmad/DocuMind.git
cd DocuMind

# Backend
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
pip install -e ".[dev]"

# Environment
cp .env.example .env               # macOS / Linux
Copy-Item .env.example .env        # Windows PowerShell
# Edit .env with your provider keys and preferences

# Frontend
cd ui && npm install
```

### Ollama OCR Models (if using local OCR)

```bash
ollama pull deepseek-ocr:3b        # General-purpose OCR
ollama pull glm-ocr                 # Structured output (headings, lists, tables)
```

## Running Locally

```bash
# Backend (http://localhost:8000)
uvicorn app.main:app --reload

# Frontend (http://localhost:5173)
cd ui && npm run dev

# Verify
curl http://localhost:8000/health/live
# → {"status": "ok"}
```

Interactive API documentation is available at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

## Configuration

All settings use the `DOCUMIND_` prefix via pydantic-settings. Provider keys (`OPENAI_API_KEY`, etc.) are also accepted without the prefix.

Copy `.env.example` to `.env` and edit as needed. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMIND_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OPENAI_API_KEY` | — | OpenAI API key (or pass per-request via BYOK) |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `DOCUMIND_VECTOR_STORE_BACKEND` | `memory` | `memory` or `milvus` |
| `DOCUMIND_JOB_QUEUE_BACKEND` | `memory` | `memory` or `redis` |
| `DOCUMIND_AUTH_ENABLED` | `false` | Enable JWT authentication |
| `DOCUMIND_MAX_UPLOAD_SIZE_MB` | `50` | Max upload file size |
| `DOCUMIND_UPLOAD_TTL_MINUTES` | `60` | Auto-cleanup uploaded files after N minutes |

For the complete variable reference (30+ settings), see [Configuration Reference](docs/usage.md#23-configuration-reference).

## Available Commands

```bash
# Backend
uvicorn app.main:app --reload                 # Dev server with hot reload
uvicorn app.main:app --host 0.0.0.0 --port 8000  # Bind to all interfaces
python -m app.workers.cli                      # Standalone worker (Redis queue mode)
pytest                                         # Run backend tests

# Frontend
cd ui
npm run dev                                    # Dev server (port 5173)
npm run build                                  # TypeScript check + production build
npm run preview                                # Preview production build
```

## Usage

The typical workflow is: **upload a document → extract text via OCR → index it → ask questions**.

```bash
# 1. Upload
curl -X POST http://localhost:8000/ocr/upload -F "file=@document.pdf"

# 2. Extract text
curl -X POST http://localhost:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/tmp/.../abc123.pdf", "prefer_structure": true}'

# 3. Index
curl -X POST http://localhost:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "my-doc", "file_path": "/tmp/.../abc123.pdf",
       "embedding_provider": "openai", "embedding_model_name": "text-embedding-3-small",
       "api_key": "sk-..."}'

# 4. Ask a question
curl -X POST http://localhost:8000/retrieval/qa \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the payment terms?",
       "provider": "openai", "model_name": "gpt-4o-mini", "api_key": "sk-...",
       "retrieval_mode": "hybrid", "use_rerank": true}'
```

### Detailed Usage Guide

For the complete feature-by-feature reference — every endpoint, parameter, response shape, and configuration option — see the **[Usage Guide](docs/usage.md)**.

<details>
<summary>Usage Guide — table of contents (23 sections)</summary>

| # | Section |
|--:|---------|
| 1 | [Before You Start](docs/usage.md#1-before-you-start) |
| 2 | [Setup & Installation](docs/usage.md#2-setup--installation) |
| 3 | [Starting the App](docs/usage.md#3-starting-the-app) |
| 4 | [Main Workflow — Step by Step](docs/usage.md#4-main-workflow--step-by-step) |
| 5 | [Health & Status](docs/usage.md#5-health--status) |
| 6 | [Provider Configuration](docs/usage.md#6-provider-configuration) |
| 7 | [OCR Extraction](docs/usage.md#7-ocr-extraction) |
| 8 | [OCR Post-Processing](docs/usage.md#8-ocr-post-processing) |
| 9 | [Text Generation](docs/usage.md#9-text-generation) |
| 10 | [Embedding Generation](docs/usage.md#10-embedding-generation) |
| 11 | [Document Indexing](docs/usage.md#11-document-indexing) |
| 12 | [Search & Retrieval](docs/usage.md#12-search--retrieval) |
| 13 | [Document QA](docs/usage.md#13-document-qa) |
| 14 | [Pipelines](docs/usage.md#14-pipelines) |
| 15 | [Background Jobs](docs/usage.md#15-background-jobs) |
| 16 | [Evaluation & Stress Testing](docs/usage.md#16-evaluation--stress-testing) |
| 17 | [Authentication](docs/usage.md#17-authentication) |
| 18 | [Web UI](docs/usage.md#18-web-ui) |
| 19 | [Input Expectations](docs/usage.md#19-input-expectations) |
| 20 | [Output & Result Behavior](docs/usage.md#20-output--result-behavior) |
| 21 | [Error States & Troubleshooting](docs/usage.md#21-error-states--troubleshooting) |
| 22 | [Limitations & Important Notes](docs/usage.md#22-limitations--important-notes) |
| 23 | [Configuration Reference](docs/usage.md#23-configuration-reference) |

</details>

## API Overview

35 endpoints organized into these groups:

| Group | Endpoints | Description |
|-------|-----------|-------------|
| `/health/*` | `GET /health/live`, `/health/ready`, `/health` | Liveness, readiness (with backend checks), legacy |
| `/info` | `GET /info` | App metadata, supported providers and engines |
| `/ocr/*` | `POST /ocr/upload`, `/ocr/route`, `/ocr/extract`, `/ocr/postprocess` | File upload, engine routing, extraction, LLM post-processing |
| `/llm/*` | `POST /llm/generate` | Direct text generation |
| `/embeddings/*` | `POST /embeddings/generate` | Vector embedding generation |
| `/retrieval/*` | `POST` index, index-ocr, search, hybrid-search, rerank, qa; `GET` documents; `DELETE` documents, documents/{doc_id} | Indexing, search, reranking, QA, document management |
| `/pipelines/*` | `GET /pipelines`, `POST /pipelines/run` | List and execute named pipelines |
| `/jobs/*` | `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` | Background job submission and polling |
| `/providers/*` | `GET /providers`, `POST /providers/{id}/models` | Provider discovery and model listing |
| `/runtime/*` | `GET /runtime/status`, `POST /runtime/activate`, `/runtime/deactivate` | Ollama model lifecycle |
| `/eval/*` | `GET /eval/benchmarks`, `POST /eval/run/{name}`, `/eval/stress` | Benchmarks and stress tests |
| `/auth/token` | `POST /auth/token` | JWT token (when auth enabled) |
| `/ui/*` | `GET /ui/config`, `/ui/forms` | Frontend configuration and form descriptors |

Full Swagger docs at `http://localhost:8000/docs`.

## Providers

| Provider | Local | Text Gen | Embeddings | BYOK |
|----------|:-----:|:--------:|:----------:|:----:|
| Ollama | ✓ | ✓ | ✓ | — |
| OpenAI | — | ✓ | ✓ | ✓ |
| Gemini | — | ✓ | ✓ | ✓ |
| Anthropic | — | ✓ | — | ✓ |

## Testing

```bash
pytest                    # Backend (16 test modules)
cd ui && npm run build    # Frontend TypeScript check + production build
```

Test coverage includes: OCR extraction, PDF handling, post-processing, providers, BYOK, embeddings, chunking, retrieval store, reranking, jobs, infrastructure (Milvus/Redis), evaluation, upload, UI schemas, response shapes, and system endpoints.

## Documentation

| Document | Description |
|----------|-------------|
| **[Usage Guide](docs/usage.md)** | Complete how-to: all endpoints, parameters, response shapes, config reference |
| [Development](docs/development.md) | Extension points for providers, OCR engines, pipelines |

## Limitations

- **OCR requires Ollama** — no cloud OCR provider is integrated. Ollama must be running locally for any OCR operation.
- **No response streaming** — all endpoints return complete JSON responses. No SSE or WebSocket support.
- **In-memory defaults lose state on restart** — vector store and job queue are in-memory by default. Use Milvus and Redis for persistence.
- **Single admin user** — authentication supports one configurable admin account. No user registration or role-based access.
- **Default credentials are insecure** — `auth_secret_key` and `auth_admin_password` ship with dev-only defaults. Change them for any non-local use.
- **Anthropic lacks embeddings** — Anthropic supports text generation only. Use Ollama, OpenAI, or Gemini for embeddings.

## Contributing

1. Branch from `main` with a focused scope.
2. Cover behavior changes with tests.
3. Update docs for any public API or configuration changes.
4. Run `pytest` and `cd ui && npm run build` before opening a PR.

See [docs/development.md](docs/development.md) for extension points.

## License

[MIT](LICENSE)
