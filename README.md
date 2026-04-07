<p align="center">
  <img src="docs/assets/documind-logo.svg" alt="DocuMind logo" width="170" />
</p>

<h1 align="center">🧠 DocuMind</h1>

<p align="center"><strong>OCR-first document intelligence platform for extracting, normalizing, structuring, indexing, and querying document content through a single API.</strong></p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img alt="React 19" src="https://img.shields.io/badge/React-19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" />
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-UI-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
  <img alt="Ollama" src="https://img.shields.io/badge/Ollama-Local%20OCR-111827?style=for-the-badge&logo=ollama&logoColor=white" />
</p>

<p align="center">
  <img alt="Hybrid Retrieval" src="https://img.shields.io/badge/Hybrid%20Retrieval-BM25%20%2B%20Vectors-0F172A?style=for-the-badge" />
  <img alt="Milvus Optional" src="https://img.shields.io/badge/Milvus-Optional%20Vector%20Store-00A1EA?style=for-the-badge&logo=milvus&logoColor=white" />
  <img alt="Redis Optional" src="https://img.shields.io/badge/Redis-Optional%20Job%20Queue-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-16A34A?style=for-the-badge" />
</p>

<p align="center">
  <img alt="OCR First" src="https://img.shields.io/badge/OCR-first-1E293B?style=flat-square" />
  <img alt="Local First" src="https://img.shields.io/badge/local-first-1E293B?style=flat-square" />
  <img alt="PDF OCR" src="https://img.shields.io/badge/PDF-multi--page%20support-1E293B?style=flat-square" />
  <img alt="RAG QA" src="https://img.shields.io/badge/RAG-QA%20with%20citations-1E293B?style=flat-square" />
  <img alt="Schema Driven UI" src="https://img.shields.io/badge/UI-schema--driven-1E293B?style=flat-square" />
</p>

DocuMind combines a FastAPI backend, a React UI, pluggable OCR engines, pluggable LLM providers, hybrid retrieval, and an evaluation harness in one local-first codebase. It can run fully on local models with Ollama or mix local OCR with cloud providers such as OpenAI, Gemini, and Anthropic.

Built with FastAPI, React 19, TypeScript, Python 3.12+, and Ollama-based OCR.

---

## ✨ Why DocuMind

Most document AI systems treat OCR as a hidden preprocessing step. DocuMind makes OCR the primary contract. Extraction, cleanup, structuring, indexing, summarization, and question answering all build on top of a concrete OCR result shape rather than burying the hard part of the problem behind a black box.

That makes the repository useful for three different audiences:

- 🛠️ engineers building document workflows without heavy infrastructure
- 🔀 teams comparing local and cloud providers behind a shared interface
- 🧪 maintainers and technical reviewers evaluating end-to-end backend and platform design in a single repository

---

## ✅ What Is Implemented

| Capability | Details |
|------------|---------|
| 📄 OCR extraction | DeepSeek-OCR and GLM-OCR via Ollama |
| 📚 Multi-page document support | Images plus multi-page PDF splitting via PyMuPDF with per-page OCR results |
| 🧹 OCR post-processing | Cleanup, summary, and key-field extraction |
| 🔌 Provider abstraction | Ollama, OpenAI, Gemini, and Anthropic behind a shared provider contract |
| 🔎 Retrieval | Dense embeddings, BM25 sparse retrieval, and weighted hybrid search |
| 🎯 Reranking | LLM-based relevance rescoring for retrieved hits |
| 💬 Document QA | Retrieval-augmented answers with source citations |
| ⏳ Async execution | Background job queue with polling and secret scrubbing (in-memory or Redis) |
| 🔐 BYOK | Per-request API keys with no browser persistence and no stored job secrets |
| 🗃️ Persistent vector store | Optional Milvus-backed retrieval store path for durable indexing |
| 📮 Persistent job queue | Optional Redis-backed job queue and persisted job records |
| 🛂 Authentication | Optional JWT-based login with configurable admin credentials |
| 🚫 Authorization | Not yet implemented beyond token validation; no RBAC or multi-user policies |
| 🧵 Multi-node workers | Standalone Redis worker CLI exists, but the API still starts its own worker by default |
| 📈 Evaluation | Benchmark suites and stress tests exposed through the API |
| 🧩 UI contract | Schema-driven forms served by the backend |

The default development mode remains local-first: in-memory stores, one API process,
and one in-process worker. Milvus, Redis, and JWT auth are optional infrastructure
paths rather than the default runtime shape.

---

## 🔌 Supported Providers

| Provider | Type | Embeddings | BYOK | Notes |
|----------|------|------------|------|-------|
| 🦙 Ollama | Local | Yes | N/A | Supports local generation and embeddings |
| 🤖 OpenAI | Cloud | Yes | Yes | Per-request key can override server environment |
| ✨ Gemini | Cloud | Yes | Yes | Same normalized response shape as other providers |
| 🪶 Anthropic | Cloud | No | Yes | Text generation only |

All providers implement the same base contract and return a normalized response with provider name, model name, generated text, token usage, and metadata.

## 👁️ Supported OCR Engines

| Engine | Model | Backend | Use case |
|--------|-------|---------|----------|
| 🔍 DeepSeek-OCR | `deepseek-ocr:3b` | Ollama | General-purpose extraction |
| 🧾 GLM-OCR | `glm-ocr` | Ollama | More structured extraction for headings, lists, and tables |

The OCR layer accepts single images (`.png`, `.jpg`, `.jpeg`, `.webp`) and multi-page PDFs (`.pdf`). PDFs are split into page images with PyMuPDF, each page is processed independently, and the final response includes both merged text and per-page OCR results.

---

## 🔄 End-to-End Flow

```text
Document (image or PDF)
          |
          v
  OCR engine selection
          |
          v
  Extract text per page or per image
          |
          v
  Normalize OCR output
          |
          v
  Structure into sections / paragraphs / tables
          |
          +----------------------+-------------------------+
          |                      |                         |
          v                      v                         v
  OCR post-process        Retrieval indexing         Named pipelines
  (cleanup / summary      (chunk / embed /           (compose steps
   / key fields)           store / search)            across services)
                                                         |
                                                         v
                                              Document QA with citations
```

---

## ⚙️ Core Workflows

| Workflow | What happens | Execution mode |
|----------|--------------|----------------|
| 📄 OCR Extract | OCR -> normalize -> structure | Direct or job |
| 📝 OCR + Summary | OCR -> LLM summarization | Direct or job |
| 🧠 OCR + Key Fields | OCR -> LLM field extraction | Direct or job |
| 🗂️ Index Document | OCR -> chunk -> embed -> store | Direct or job |
| 💬 Ask Indexed Documents | Retrieve -> optional rerank -> answer with citations | Direct or job |
| 🧪 Run Pipeline | Execute a named multi-step pipeline | Direct or job |

Available named pipelines:

- `ocr_extract_only`
- `ocr_extract_then_summary`
- `ocr_extract_then_key_fields`

---

## 📄 Example: OCR A Multi-Page PDF

```bash
curl -X POST http://127.0.0.1:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/absolute/path/to/document.pdf",
    "prefer_structure": true
  }'
```

Response shape excerpt:

```json
{
  "engine": "glm-ocr",
  "layout": {
    "pages": 3,
    "structure": true
  },
  "text": "...merged OCR text...",
  "pages": [
    {
      "page": 1,
      "text": "...page 1 text...",
      "confidence": 0.0,
      "metadata": {
        "model": "glm-ocr"
      }
    },
    {
      "page": 2,
      "text": "...page 2 text...",
      "confidence": 0.0,
      "metadata": {
        "model": "glm-ocr"
      }
    }
  ]
}
```

For the complete API surface, see [docs/api-overview.md](docs/api-overview.md).

---

## 🏗️ Architecture At A Glance

```text
React UI (Vite + TypeScript)
          |
          v
FastAPI application
  |- route handlers
  |- OCR engines
  |- provider adapters
  |- retrieval services
  |- evaluation suite
  |- job queue facade (memory or Redis)
  |- retrieval store facade (memory or Milvus)
          |
          v
External runtimes / APIs
  |- Ollama
  |- OpenAI
  |- Gemini
  |- Anthropic
  |- Milvus (optional)
  `- Redis (optional)
```

Key architectural characteristics:

- single-process application with no database or broker required for local development
- in-memory defaults for low-friction local setup, with optional Milvus and Redis backends
- provider abstraction that separates request routing from vendor-specific SDK logic
- OCR normalization and structuring kept as explicit stages instead of hidden internals
- schema-driven UI where the backend serves frontend-safe form metadata

Current infrastructure caveats:

- JWT auth currently verifies bearer tokens but does not implement role-based authorization.
- A standalone worker process exists for Redis-backed queues, but the API still launches an in-process worker on startup.
- Readiness checks stay lightweight and do not validate Milvus or Redis connectivity.
- Swagger UI is available at `/docs`, but the built-in OAuth redirect flow is not fully polished when auth is enabled.

See [docs/architecture.md](docs/architecture.md) for module-level detail and request flow diagrams.

---

## 🚀 How To Run

You can run the full stack locally with one Python backend process and one Vite frontend process. Ollama is optional unless you want to use local OCR or local-model flows.

### 🧰 Prerequisites

- Python 3.12+
- Node.js 18+
- Ollama, if you want local OCR or local-model workflows

### 🖥️ Backend

```bash
python -m venv .venv

python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1

Copy-Item .env.example .env

uvicorn app.main:app --reload
```

macOS / Linux:

```bash
source .venv/bin/activate

cp .env.example .env

uvicorn app.main:app --reload
```

API: `http://127.0.0.1:8000`

Interactive API docs: `http://127.0.0.1:8000/docs`

When JWT auth is enabled, the docs remain visible, but the built-in Swagger auth redirect flow still needs cleanup.

### 🎨 Frontend

```bash
cd ui
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

Set `VITE_API_BASE_URL` if the backend is running on a different host or port.

### 🦙 Optional Ollama Setup

```bash
ollama pull deepseek-ocr:3b
ollama pull glm-ocr
```

The default runtime URL is `http://localhost:11434` via `DOCUMIND_OLLAMA_BASE_URL`.

### 🧪 Tests And Build

```bash
pytest
cd ui && npm run build
```

The repository includes automated backend coverage across OCR, providers, retrieval, jobs, and evaluation, and the frontend supports a production build through Vite.

---

## 🗂️ Repository Layout

```text
DocuMind/
|- app/
|  |- api/           # FastAPI route handlers
|  |- core/          # settings, middleware, errors, pipelines, model manager
|  |- eval/          # benchmarks, evaluator, metrics, stress tests
|  |- ocr/           # OCR engines, PDF splitting, normalization, structuring
|  |- providers/     # provider adapters and registry
|  |- schemas/       # request and response models
|  |- services/      # indexing, retrieval, reranking, QA, post-processing
|  `- workers/       # queue facade, background worker, and standalone worker CLI
|- docs/             # architecture, API, workflows, development notes
|- tests/            # backend test suite
`- ui/               # React 19 + TypeScript + Vite frontend
```

---

## ⚖️ Engineering Decisions

| Decision | Why it was chosen | Tradeoff |
|----------|-------------------|----------|
| In-memory defaults | Keeps local setup simple and fast | Durability and distributed execution require extra infrastructure |
| API-managed worker startup | One command starts the whole backend | The API still runs a local worker even when Redis-backed workers are available |
| Per-request provider selection | Supports local and cloud models behind one API | More request validation and branching at runtime |
| BYOK instead of stored credentials | Avoids persistent secret management in the app | Callers must provide keys when environment defaults are absent |
| OCR normalization as an explicit stage | Makes downstream quality improvements visible and testable | Adds an extra transformation layer to the pipeline |
| LLM-based reranking | Works across providers without extra model infrastructure | Higher latency and cost than a dedicated reranker |
| Schema-driven UI | Keeps the frontend aligned with backend capabilities | Requires backend-maintained form metadata |

---

## 🧪 Verification

DocuMind is not just a collection of endpoints. The repository includes explicit validation for the main workflow layers:

- OCR and OCR post-processing tests
- provider and BYOK tests
- embedding, retrieval, and reranking tests
- jobs and system health tests
- evaluation and stress-test coverage
- dedicated tests for multi-page PDF OCR support

The API also exposes evaluation endpoints for smoke-style benchmarks and concurrent stress runs under `/eval`.

Current test coverage is strongest around the default in-memory execution path, auth helpers,
and backend-selection facades. Live Redis and Milvus integration coverage is not yet part of
the automated suite.

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [docs/user-guide.md](docs/user-guide.md) | Full how-to guide — setup, every feature, curl examples, env vars |
| [docs/architecture.md](docs/architecture.md) | Module map, request flows, and system boundaries |
| [docs/api-overview.md](docs/api-overview.md) | Endpoint groups, job mode, and BYOK behavior |
| [docs/workflows.md](docs/workflows.md) | Example payloads and end-to-end workflow walkthroughs |
| [docs/development.md](docs/development.md) | Local setup and extension points for providers, OCR, and pipelines |
| [ui/README.md](ui/README.md) | Frontend structure and component-level notes |

---

## 🤝 Contributing

Contributions are welcome, especially in areas that strengthen the core platform and improve the developer or user experience.

Preferred contribution areas:

- OCR engine improvements and additional OCR adapters
- retrieval quality, reranking behavior, and evaluation coverage
- provider integrations and runtime ergonomics
- developer experience, testing, and production-readiness improvements
- frontend clarity and workflow usability improvements

Contribution guidelines:

1. Create a focused branch for a single change or tightly related set of changes.
2. Keep behavior changes covered by tests whenever practical.
3. Update docs when you change the public API, workflow behavior, or setup steps.
4. Run `pytest` for backend changes and `cd ui && npm run build` for frontend changes before opening a PR.
5. Prefer incremental, reviewable changes over broad refactors that mix behavior, style, and restructuring.

If you are extending providers, OCR engines, or pipelines, start with [docs/development.md](docs/development.md).

---

## 📄 License

This project is available under the [MIT License](LICENSE).

---

## 🎯 Current Scope

This repository is intentionally optimized for development, experimentation, and architecture clarity.

Current non-goals:

- no containerized deployment stack in-repo
- no benchmark-backed claim of production OCR accuracy

---

## 🔭 Future Scope

The next meaningful extensions are the ones that improve durability, operability, and model breadth without breaking the current local-first development experience.

- additional OCR engines such as Tesseract or Azure Document Intelligence
- additional provider integrations such as Bedrock or Mistral
- role-based access control and multi-user support
- clean API-only versus worker-only deployment modes
- backend-aware readiness checks and external-service integration coverage
- CI coverage gates, linting, and type-checking in pipeline form
- Docker Compose for one-command local bring-up
- tracing and observability improvements
