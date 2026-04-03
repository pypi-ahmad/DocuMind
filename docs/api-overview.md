# API Overview

DocuMind exposes a REST API organized into endpoint groups. Interactive
documentation is available at `/docs` (Swagger UI) when the server is running.

---

## Endpoint Groups

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/live` | Liveness probe — confirms the process is running |
| GET | `/health/ready` | Readiness probe — checks queue and model manager |
| GET | `/health` | Legacy health check |
| GET | `/info` | App name, version, supported engines |

### Providers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/providers` | List supported providers and capability flags |
| POST | `/providers/{provider}/models` | List models available from a provider |

Accepts an optional `api_key` in the request body for BYOK cloud providers.

### OCR

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ocr/route` | Return the OCR engine decision for a document request |
| POST | `/ocr/extract` | Run OCR with a selected or auto-routed engine |
| POST | `/ocr/postprocess` | Summarize or extract key fields from OCR output |

### LLM

| Method | Path | Description |
|--------|------|-------------|
| POST | `/llm/generate` | Generate text with any supported provider |

### Embeddings

| Method | Path | Description |
|--------|------|-------------|
| POST | `/embeddings/generate` | Generate vector embeddings for a text input |

### Retrieval

| Method | Path | Description |
|--------|------|-------------|
| POST | `/retrieval/index` | Chunk, embed, and index plain document text |
| POST | `/retrieval/index-ocr` | Extract, chunk, embed, and index a document |
| POST | `/retrieval/search` | Dense vector search over indexed documents |
| POST | `/retrieval/hybrid-search` | Combined dense + BM25 sparse search |
| POST | `/retrieval/rerank` | Re-score a set of search results |
| POST | `/retrieval/qa` | Answer a question grounded in indexed documents |
| GET | `/retrieval/documents` | List indexed document summaries |
| DELETE | `/retrieval/documents` | Clear all indexed documents |

### Pipelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines` | List available named pipeline definitions |
| POST | `/pipelines/run` | Execute a named pipeline with provided input |

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Submit a background job |
| GET | `/jobs/{job_id}` | Poll job status and retrieve results |
| GET | `/jobs` | List all tracked in-memory jobs |

### Runtime

| Method | Path | Description |
|--------|------|-------------|
| GET | `/runtime/status` | Current active model and runtime state |
| POST | `/runtime/activate` | Activate a model on the Ollama runtime |
| POST | `/runtime/deactivate` | Deactivate the current runtime model |

### Evaluation

| Method | Path | Description |
|--------|------|-------------|
| GET | `/eval/benchmarks` | List available benchmark suites |
| POST | `/eval/run/{benchmark_name}` | Run a benchmark suite |
| POST | `/eval/stress` | Run a stress / load test |

### UI Contract

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ui/config` | Frontend capability discovery (providers, engines, routes) |
| GET | `/ui/forms` | Field-level metadata for each action form |

---

## Direct Mode vs Job Mode

Most actions support two submission paths:

### Direct mode

The client sends a request to the action endpoint (e.g. `POST /ocr/extract`)
and blocks until the response is ready.

### Job mode

The client sends a request to `POST /jobs` with a `type` and `input` payload.
The server returns a `JobResponse` immediately with `status: pending`. The client
polls `GET /jobs/{job_id}` until the status reaches `completed` or `failed`.

| Action | Job type string |
|--------|----------------|
| `ocr_extract` | `ocr.extract` |
| `ocr_postprocess` | `ocr.postprocess` |
| `retrieval_index_ocr` | `retrieval.index_ocr` |
| `retrieval_qa` | `retrieval.qa` |
| `pipeline_run` | `pipeline.run` |

`llm_generate` is direct-only in the current implementation.

---

## Provider and Model Selection

Actions that involve an LLM require `provider` and `model_name` in the request
body. The available providers are:

| Provider | How model is resolved |
|----------|-----------------------|
| `ollama` | Model activated via runtime manager; caller specifies model name |
| `openai` | Model name passed to OpenAI API |
| `gemini` | Model name passed to Google GenAI API |
| `anthropic` | Model name passed to Anthropic API |

Use `POST /providers/{provider}/models` to fetch available models dynamically.

---

## BYOK (Bring Your Own Key)

Cloud providers (`openai`, `gemini`, `anthropic`) accept an optional `api_key`
field in the request body.

- **If provided** — the per-request key is used for that single call and takes
  priority over any server-side `.env` key.
- **If omitted** — the backend falls back to `DOCUMIND_OPENAI_API_KEY`,
  `DOCUMIND_GEMINI_API_KEY`, or `DOCUMIND_ANTHROPIC_API_KEY` from the environment.
- **In job mode** — the API key is stored separately from the visible job input,
  re-attached at execution time, and cleared after the job completes.
- **In the UI** — the key is held only in React component state and is never
  persisted to any browser storage.
