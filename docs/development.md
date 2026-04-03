# Development Guide

## Local Setup

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Required |
| Node.js | 18+ | For the frontend only |
| Ollama | Latest | Optional — needed for local LLM / OCR engines |

### Backend

```bash
# Clone the repository
git clone <repo-url>
cd DocuMind

# Create a virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux / macOS)
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Edit .env with your keys

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.
Swagger docs at `http://127.0.0.1:8000/docs`.

### Frontend

```bash
cd ui
npm install
npm run dev
```

The Vite dev server starts on `http://localhost:5173`.
Set `VITE_API_BASE_URL` if the backend runs on a different host/port.

### Run Tests

```bash
# All tests
pytest

# Verbose with short tracebacks
pytest --tb=short -v

# Specific test file
pytest tests/test_ocr.py
```

### Build Frontend for Production

```bash
cd ui
npm run build
```

Output goes to `ui/dist/`.

---

## Project Layout

```
app/
├── api/routes/     # HTTP route handlers
├── core/           # Settings, middleware, pipelines, errors
├── providers/      # LLM provider adapters (BaseProvider ABC)
├── ocr/            # OCR engine adapters (BaseOCREngine ABC)
├── services/       # Domain logic (indexing, QA, reranking, etc.)
├── workers/        # In-memory async job queue + worker
├── eval/           # Benchmarks, evaluator, metrics, stress tests
└── schemas/        # Pydantic request/response models
```

---

## Where to Add New Providers

1. Create `app/providers/<name>.py` implementing `BaseProvider` from
   `app/providers/base.py`.
2. Register the provider in `app/providers/registry.py`.
3. Add the provider's API key field to `app/core/settings.py` if it needs
   server-side credentials.
4. Add tests in `tests/test_providers.py` (or a new test file).

The `BaseProvider` ABC requires:

- `generate(prompt, model_name, **kwargs) -> ProviderResponse`

All providers must return a normalized response with `text`, `usage`, and
`metadata` fields.

---

## Where to Add New OCR Engines

1. Create `app/ocr/<name>.py` implementing `BaseOCREngine` from
   `app/ocr/base.py`.
2. Register the engine in `app/ocr/router.py` so the auto-router can select it.
3. Add relevant settings to `app/core/settings.py` if needed (e.g. model name).
4. Add tests in `tests/test_ocr.py`.

The `BaseOCREngine` ABC requires:

- `extract(image_data, prefer_structure) -> OCRResult`

---

## Where to Add New Pipelines

Pipeline definitions live in `app/core/pipelines.py`. Each pipeline is a
`PipelineDefinition` with:

- `name` — unique identifier
- `description` — human-readable summary
- `steps` — ordered tuple of `PipelineStepDefinition` objects
- `required_input_fields` / `optional_input_fields`

Steps reference existing step kinds (`ocr_extract`, `ocr_postprocess`). The
pipeline runner in `app/services/pipeline_runner.py` dispatches each step.

To add a pipeline, add an entry to the `PIPELINE_DEFINITIONS` dict in
`app/core/pipelines.py`. No route changes are needed — `GET /pipelines` and
`POST /pipelines/run` discover definitions dynamically.

---

## Where to Add Benchmarks / Stress Tests

### Benchmarks

Benchmark suites are defined in `app/eval/benchmarks.py`. Each benchmark
specifies inputs, expected outputs, and scoring criteria.

The evaluator in `app/eval/evaluator.py` runs them and reports metrics defined
in `app/eval/metrics.py`.

### Stress Tests

The stress test driver lives in `app/eval/stress.py`. It sends concurrent
requests to measure throughput and latency under load. Triggered via
`POST /eval/stress`.

---

## Environment Variables

All DocuMind settings are defined in `app/core/settings.py` using
pydantic-settings. The prefix `DOCUMIND_` is used for environment variable
resolution, but alias-based resolution also supports bare names (e.g.
`OPENAI_API_KEY` resolves the same as `DOCUMIND_OPENAI_API_KEY`).

See `.env.example` for a reference of available variables.

---

## Frontend Stack

| Technology | Purpose |
|-----------|---------|
| React 19 | UI framework |
| TypeScript | Type safety |
| Vite | Dev server and bundler |

The frontend has no external state management library — all state lives in
React `useState` hooks in `App.tsx`. API calls are in `ui/src/api.ts` with
typed responses from `ui/src/types.ts`.
