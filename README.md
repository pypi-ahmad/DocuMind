# DocuMind

**OCR-first document intelligence platform** — extract, normalize, structure, index, and query document content through pluggable LLM providers with a single self-hosted API.

Built with FastAPI · React · TypeScript · Python 3.12+

---

## Why This Project Exists

Most document processing tools treat OCR as an afterthought — a preprocessing step buried inside a larger pipeline. DocuMind inverts that: OCR extraction is the primary entry point, and everything downstream (normalization, summarization, field extraction, retrieval, QA) is composed on top of clean, structured OCR output.

The result is a system that demonstrates how to build a practical document intelligence API with:

- A **pluggable provider layer** so the same workflow runs against Ollama locally or OpenAI/Gemini/Anthropic in the cloud — swapped per-request, not per-deployment
- A **BYOK (Bring Your Own Key) model** where API keys are injected per-request and never persisted
- An **async job queue** decoupling request acceptance from execution
- **Hybrid retrieval** combining dense vector search with BM25 sparse scoring
- A **built-in evaluation framework** with benchmarks and stress tests to validate OCR and retrieval quality

---

## What the System Does

```
Document Image
      │
      ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  OCR Engine  │────▶│  Normalize   │────▶│  Structure       │
│  (pluggable) │     │  + Clean     │     │  (sections,      │
└─────────────┘     └──────────────┘     │   paragraphs,    │
                                          │   tables)        │
                                          └────────┬─────────┘
                                                   │
                          ┌────────────────────────┼────────────────────┐
                          ▼                        ▼                    ▼
                   ┌─────────────┐          ┌────────────┐      ┌────────────┐
                   │ Postprocess │          │  Chunk +   │      │  Pipeline  │
                   │ (summary,   │          │  Embed +   │      │  Runner    │
                   │  key fields,│          │  Index     │      │  (named    │
                   │  cleanup)   │          └─────┬──────┘      │   steps)   │
                   └─────────────┘                │             └────────────┘
                                                  ▼
                                     ┌────────────────────────┐
                                     │  Hybrid Search         │
                                     │  (dense + BM25 sparse) │
                                     │  + LLM Reranking       │
                                     └───────────┬────────────┘
                                                  ▼
                                     ┌────────────────────────┐
                                     │  Document QA           │
                                     │  (RAG with citations)  │
                                     └────────────────────────┘
```

Every box in this diagram is implemented. The backend flows shown here are covered by the test suite, and the API route groups are backed by concrete handlers rather than placeholder endpoints.

---

## Engineering Highlights

These are aspects of the implementation that reflect deliberate design, not incidental complexity:

| Area | What's implemented |
|------|--------------------|
| **Provider abstraction** | `BaseProvider` ABC with four concrete implementations (Ollama, OpenAI, Gemini, Anthropic). All return a normalized `ProviderGenerateResult` — provider, model, text, token usage, metadata. Swappable per-request. |
| **BYOK key injection** | Per-request `api_key` field overrides `.env` fallback. Keys held in React state only — never written to storage, cookies, or URLs. Cleared from job records after execution. |
| **OCR → Normalize → Structure pipeline** | Raw OCR output is cleaned (blank lines, whitespace, hyphenation, line breaks) then structured into sections, paragraphs, lines, and table candidates. Downstream services choose the best representation. |
| **Hybrid retrieval** | Dense search (cosine similarity on embeddings) merged with sparse search (BM25L via `rank-bm25`) using configurable `dense_weight` / `sparse_weight` blending with min-max normalization. |
| **LLM-based reranking** | Each candidate hit is scored for relevance (0–1) by a provider call. Final score is the average of original retrieval score and rerank score. Top-k filtering applied post-rerank. |
| **Async job system** | In-memory `asyncio.Queue` with a background worker task. Jobs transition through `pending` → `processing` → `completed` / `failed`. API keys are scrubbed from job records after execution. |
| **Named pipelines** | Static pipeline definitions with typed step sequences, required/optional input fields, and step-result threading. Each step's output feeds the next step's input. |
| **Evaluation framework** | Four benchmark suites (OCR, retrieval, reranking, QA) with per-case assertions. Three stress test types (job submission, retrieval search, document QA) reporting throughput, p95 latency, and success rate. |
| **Schema-driven UI** | Backend serves form descriptors via `GET /ui/forms`. The React frontend renders field inputs dynamically for the supported actions instead of maintaining separate hand-written forms for each one. |
| **Middleware** | Request ID injection (`X-Request-ID` header) and request timing (`X-Process-Time-MS` header) applied to every response. |

---

## Architecture

```
┌──────────────┐   HTTP   ┌──────────────────────────────────────────────────┐
│  React UI    │ ──────── │  FastAPI (single process)                        │
│  (Vite +     │          │                                                  │
│   TypeScript)│          │  11 route groups ─► service layer ─► providers   │
└──────────────┘          │       │                    │                      │
                          │       ▼                    ▼                      │
                          │  async job queue     OCR engines (Ollama)         │
                          │  (in-memory)         normalization + structuring  │
                          │       │                                           │
                          │       ▼                                           │
                          │  eval: benchmarks + stress tests                  │
                          └──────────────────────────────────────────────────┘
```

**Single process, minimal infrastructure.** No database, message broker, or container setup is required to run locally. The entire system runs with `uvicorn app.main:app`, with Ollama needed only for local OCR and local-model workflows.

**Route groups:** system · providers · LLM · embeddings · OCR · retrieval · pipelines · jobs · runtime · eval · UI

See [docs/architecture.md](docs/architecture.md) for module-level detail and request flow diagrams.

---

## Supported Providers

| Provider | Type | Embedding support | BYOK | Notes |
|----------|------|-------------------|------|-------|
| **Ollama** | Local | Yes | N/A | Models managed via runtime activate/deactivate |
| **OpenAI** | Cloud | Yes | Yes | Per-request key overrides `.env` fallback |
| **Gemini** | Cloud | Yes | Yes | Same normalized response shape as all providers |
| **Anthropic** | Cloud | No | Yes | Text generation only; no embedding support |

All providers implement `BaseProvider` and return a uniform `ProviderGenerateResult` (provider name, model name, generated text, token usage, metadata).

## Supported OCR Engines

| Engine | Model | Backend | Use case |
|--------|-------|---------|----------|
| **DeepSeek-OCR** | `deepseek-ocr:3b` | Ollama | Default general-purpose OCR extraction |
| **GLM-OCR** | `glm-ocr` | Ollama | Structured-oriented extraction for headings, lists, and tables |

An `OCRRouter` selects the engine automatically (`deepseek-ocr` by default, `glm-ocr` when `prefer_structure=True`), or the caller can specify explicitly.

---

## BYOK (Bring Your Own Key)

- A per-request `api_key` in the request body **overrides** the server `.env` fallback for that single call
- The React UI holds keys **only in component state** — never written to localStorage, sessionStorage, cookies, URLs, or backend storage
- The backend **scrubs API keys from job records** after execution via `clear_job_secrets()`
- If no key is provided and no `.env` key is configured, the request fails with a clear error

---

## Core Workflows

| Workflow | Steps | Submission |
|----------|-------|------------|
| **OCR Extract** | Extract text via OCR engine → normalize → structure | Direct or job queue |
| **OCR + Summary** | OCR extract → LLM-powered summarization | Direct or job queue |
| **OCR + Key Fields** | OCR extract → LLM-powered field extraction | Direct or job queue |
| **Index Document** | OCR extract → chunk → embed → store in retrieval index | Direct or job queue |
| **Document QA** | Query → hybrid search → optional reranking → RAG answer with citations | Direct or job queue |
| **Named Pipeline** | Execute a defined multi-step pipeline by name | Direct or job queue |

**Available pipelines:** `ocr_extract_only`, `ocr_extract_then_summary`, `ocr_extract_then_key_fields`

The core workflows have both **direct execution** (synchronous response) and **job queue submission** (async with polling) paths at the API level. In the UI, supported actions expose a direct/job toggle.

See [docs/workflows.md](docs/workflows.md) for step-by-step walkthroughs.

---

## UI Overview

The frontend is a React 19 + TypeScript + Vite application that acts as a thin client over the backend API.

- **Workflow presets** — six guided presets (OCR Extract, OCR + Summary, OCR + Key Fields, Index Document, Ask Indexed Documents, Run Pipeline) that pre-fill the correct action, endpoint, and form fields
- **Schema-driven forms** — the backend serves form descriptors (`GET /ui/forms`); the UI renders fields dynamically based on type (string, boolean, integer, number, JSON object)
- **Provider & model selectors** — separate selectors for LLM and embedding providers/models, populated from `GET /providers/{provider}/models`
- **Pipeline selector** — dropdown populated from `GET /pipelines` with fallback to manual entry
- **Indexed document list** — shows currently indexed documents from `GET /retrieval/documents`
- **Direct / job toggle** — submit supported actions synchronously or via the async job queue with automatic polling
- **Request preview** — inspect the outgoing payload before submission (API keys redacted)
- **BYOK input** — per-provider API key field, held only in React state

---

## Evaluation & Stress Testing

DocuMind includes a built-in evaluation framework accessible via the `/eval` route group.

**Benchmark suites** (`POST /eval/run/{benchmark_name}`):

| Suite | Cases | What it validates |
|-------|-------|-------------------|
| `ocr_smoke` | 4 | OCR extraction shape, normalization correctness |
| `retrieval_smoke` | 4 | Dense and hybrid retrieval hit presence |
| `rerank_smoke` | 3 | Reranked result quality — relevant hit near top |
| `qa_smoke` | 4+ | QA grounding, keyword presence, citation structure |

**Stress tests** (`POST /eval/stress`):

| Type | What it measures |
|------|------------------|
| `job_submit` | Concurrent job submission throughput |
| `retrieval_search` | Concurrent dense/hybrid search latency |
| `document_qa` | Concurrent QA call performance |

Stress test results include: total/successful/failed requests, average latency, p95 latency (nearest-rank), and throughput (requests/sec).

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the frontend)
- [Ollama](https://ollama.com/) running locally (optional — needed only for local LLM / OCR)

### Backend

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"

cp .env.example .env
# Edit .env — add API keys for cloud providers if desired

uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000` · Interactive docs: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd ui
npm install
npm run dev
```

Opens at `http://localhost:5173`. Set `VITE_API_BASE_URL` to override the default backend URL.

### Ollama (optional)

```bash
ollama pull deepseek-ocr:3b
ollama pull glm-ocr
```

Ensure Ollama is running at `http://localhost:11434` (the default `DOCUMIND_OLLAMA_BASE_URL`).

### Tests

```bash
pytest
```

125+ tests covering OCR, providers, retrieval, reranking, QA, jobs, BYOK, chunking, evaluation, and system health.

---

## Repository Structure

```
DocuMind/
├── app/
│   ├── main.py                 # FastAPI entry point — lifespan, middleware, routers
│   ├── api/
│   │   ├── router.py           # Root API router
│   │   └── routes/             # 11 route modules (ocr, llm, retrieval, jobs, …)
│   ├── core/
│   │   ├── settings.py         # pydantic-settings config (DOCUMIND_ prefix)
│   │   ├── pipelines.py        # Named pipeline definitions
│   │   ├── model_manager.py    # Runtime model activation / deactivation
│   │   ├── errors.py           # Global exception handlers
│   │   ├── middleware.py        # Request ID + timing middleware
│   │   └── logging.py          # Structured logging setup
│   ├── providers/
│   │   ├── base.py             # BaseProvider ABC + ProviderGenerateResult
│   │   ├── registry.py         # Provider factory registry
│   │   ├── ollama.py           # Local Ollama provider
│   │   ├── openai.py           # OpenAI provider
│   │   ├── gemini.py           # Google Gemini provider
│   │   └── anthropic.py        # Anthropic provider
│   ├── ocr/
│   │   ├── base.py             # BaseOCREngine ABC
│   │   ├── router.py           # Engine selection logic
│   │   ├── normalize.py        # OCR text normalization
│   │   ├── structure.py        # Section/paragraph/table structuring
│   │   ├── deepseek.py         # DeepSeek-OCR engine
│   │   └── glm.py              # GLM-OCR engine
│   ├── services/
│   │   ├── ocr_postprocess.py  # LLM-powered summarization / key-field extraction
│   │   ├── indexing.py         # OCR → chunk → embed → store
│   │   ├── chunking.py         # Paragraph-aware chunking with overlap
│   │   ├── embedding_service.py# Embedding generation + document indexing
│   │   ├── retrieval_store.py  # In-memory vector store (cosine similarity)
│   │   ├── sparse_retrieval.py # BM25L sparse search (rank-bm25)
│   │   ├── hybrid_retrieval.py # Weighted dense + sparse score merging
│   │   ├── reranker.py         # LLM-based relevance reranking
│   │   ├── document_qa.py      # Retrieval-augmented QA with citations
│   │   └── pipeline_runner.py  # Named pipeline executor
│   ├── workers/
│   │   ├── queue.py            # In-memory async job queue
│   │   └── worker.py           # Background job processor (5 job types)
│   ├── eval/
│   │   ├── benchmarks.py       # 4 benchmark suites (OCR, retrieval, rerank, QA)
│   │   ├── evaluator.py        # Benchmark runner with per-case assertions
│   │   ├── metrics.py          # Scoring functions
│   │   └── stress.py           # 3 stress test types with p95/throughput metrics
│   └── schemas/                # Pydantic request/response models
├── tests/                      # 12 test modules (125+ tests)
├── ui/                         # React 19 + TypeScript + Vite
│   └── src/
│       ├── App.tsx             # Workflow preset orchestration
│       ├── api.ts              # Typed API client
│       ├── types.ts            # Shared TypeScript types
│       └── components/         # Reusable UI components
├── docs/                       # Extended documentation
├── .env.example                # Annotated environment variable template
├── pyproject.toml              # Python project metadata
└── README.md
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | System overview, module map, request flow diagrams |
| [docs/api-overview.md](docs/api-overview.md) | All endpoint groups, direct vs. job mode, BYOK details |
| [docs/workflows.md](docs/workflows.md) | Step-by-step workflow walkthroughs with example payloads |
| [docs/development.md](docs/development.md) | Local setup, extending providers / engines / pipelines |
| [ui/README.md](ui/README.md) | Frontend architecture and component documentation |

---

## Design Decisions & Tradeoffs

| Decision | Rationale |
|----------|-----------|
| **In-memory stores** | Eliminates infrastructure dependencies for local development. Tradeoff: data is lost on restart. |
| **Single-process async worker** | Keeps deployment simple (one `uvicorn` command). Tradeoff: no horizontal scaling. |
| **Per-request provider selection** | Allows the same API to serve local Ollama and cloud providers without redeployment. |
| **BYOK over server-managed keys** | Avoids key storage responsibility. The API never persists caller secrets. |
| **Schema-driven UI forms** | Backend controls field shape for supported actions; the frontend stays generic at the form level instead of maintaining a separate hand-built form per action. |
| **OCR normalization as a separate stage** | Keeps raw OCR output available while providing a clean version for downstream use. |
| **Hybrid retrieval with configurable weights** | Dense search captures semantics; BM25 captures exact terms. Weights let the caller tune the blend. |
| **LLM-based reranking (not cross-encoder model)** | Works with any text generation provider; no additional model infrastructure required. |

---

## Non-Goals / Out of Scope

These are intentionally excluded from the current implementation:

- **Production deployment** — no Docker, Kubernetes, or CI/CD. This is a development/demonstration system.
- **Persistent storage** — retrieval index and job queue are in-memory by design.
- **Authentication / authorization** — the API is open. Deploy behind a gateway for access control.
- **Multi-node scaling** — single-process architecture; the job worker runs in the same process.
- **PDF page splitting** — OCR operates on single images; multi-page PDF support is not implemented.
- **Fine-tuned OCR accuracy claims** — both engines run via Ollama with default prompts; no accuracy benchmarks are published.

---

## Future Improvements

- Persistent vector store backend (Qdrant, Weaviate, or pgvector)
- Persistent job queue (Redis or Celery)
- Authentication and API key management
- PDF page-level OCR with multi-page support
- Additional OCR engines (Tesseract, Azure Document Intelligence)
- Additional LLM providers (AWS Bedrock, Mistral)
- CI/CD pipeline with linting, type-checking, and coverage gates
- Docker Compose for one-command local setup
- OpenTelemetry tracing integration

---

## Resume / Interview Talking Points

These are grounded in the actual implementation — not aspirational:

1. **Designed a pluggable provider abstraction** over four LLM backends (Ollama, OpenAI, Gemini, Anthropic) with a uniform response contract (`ProviderGenerateResult`), enabling per-request provider switching without configuration changes.

2. **Implemented hybrid document retrieval** combining dense vector search (cosine similarity on embeddings) with BM25L sparse scoring, merged via configurable weighted blending with min-max normalization.

3. **Built an LLM-based reranking layer** that scores each retrieval hit for relevance (0–1) and produces a final score as a weighted average of retrieval and rerank scores for downstream RAG workflows.

4. **Engineered a BYOK key injection model** where per-request API keys override server-side defaults, are never persisted to disk or browser storage, and are scrubbed from job records after execution.

5. **Implemented an OCR normalization and structuring pipeline** that cleans raw OCR output (whitespace, hyphenation, broken lines) and extracts sections, paragraphs, and table candidates for downstream consumption.

6. **Built a schema-driven frontend** where the backend serves form descriptors and the React UI renders input forms dynamically for supported actions, reducing the need for separate hand-built forms.

7. **Created an async job system** with an in-memory `asyncio.Queue`, background worker, four-state lifecycle (`pending` → `processing` → `completed` / `failed`), and automatic secret scrubbing.

8. **Developed a built-in evaluation framework** with four benchmark suites and three stress test types reporting throughput, p95 latency, and success rate for validating OCR and retrieval quality.
