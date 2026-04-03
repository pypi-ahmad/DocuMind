# Workflows

Step-by-step walkthroughs for the most common DocuMind workflows. All examples
use `curl` against `http://localhost:8000`.

---

## 1. OCR Extract

Extract text from a document image or multi-page PDF.

```bash
curl -X POST http://localhost:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/document.png",
    "prefer_structure": true
  }'
```

The backend auto-selects an OCR engine, or you can specify one:

```bash
  "engine": "deepseek-ocr"
```

**Response** includes the extracted text, engine used, and structured output.

---

## 2. OCR + Summary

Two-step flow: extract OCR text, then summarize it with an LLM.

### Step 1 — Extract

```bash
curl -X POST http://localhost:8000/ocr/extract \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/document.png"
  }'
```

Save the response (the full OCR result object).

### Step 2 — Summarize

```bash
curl -X POST http://localhost:8000/ocr/postprocess \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summary",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "ocr_result": { ... }
  }'
```

Replace `{ ... }` with the OCR result from Step 1.

> **Tip:** The UI's "OCR + Summary" preset automates both steps in the browser —
> it runs OCR extract first and pipes the result into post-process automatically.

---

## 3. OCR + Key Fields

Same two-step structure as OCR + Summary, but with `task: "extract_key_fields"`.

### Step 1 — Extract

(Same as above.)

### Step 2 — Extract key fields

```bash
curl -X POST http://localhost:8000/ocr/postprocess \
  -H "Content-Type: application/json" \
  -d '{
    "task": "extract_key_fields",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "ocr_result": { ... }
  }'
```

---

## 4. OCR Index Document

Extract OCR content and index it into the retrieval store in a single request.

```bash
curl -X POST http://localhost:8000/retrieval/index-ocr \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "invoice-001",
    "file_path": "/path/to/document.png",
    "embedding_provider": "openai",
    "embedding_model_name": "text-embedding-3-small",
    "api_key": "sk-...",
    "prefer_structure": true
  }'
```

The backend extracts OCR output, chunks it, generates embeddings, and stores
everything in the in-memory retrieval store.

---

## 5. Ask Indexed Documents

Query already-indexed documents with retrieval-augmented QA.

```bash
curl -X POST http://localhost:8000/retrieval/qa \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the total amount on invoice 001?",
    "provider": "openai",
    "model_name": "gpt-4o-mini",
    "api_key": "sk-...",
    "retrieval_mode": "hybrid",
    "use_rerank": true,
    "top_k": 5
  }'
```

Returns an answer grounded in the retrieved document chunks.

You can list what's currently indexed:

```bash
curl http://localhost:8000/retrieval/documents
```

---

## 6. Run Named Pipeline

Execute a predefined multi-step pipeline by name.

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
      "file_path": "/path/to/document.png",
      "provider": "openai",
      "model_name": "gpt-4o-mini",
      "api_key": "sk-..."
    }
  }'
```

The pipeline executes each step in sequence. Current built-in pipelines:

| Pipeline name | Steps |
|--------------|-------|
| `ocr_extract_only` | OCR extract |
| `ocr_extract_then_summary` | OCR extract → summarize |
| `ocr_extract_then_key_fields` | OCR extract → extract key fields |

---

## Job Mode

Any of the above workflows (except `llm_generate`) can be submitted as a
background job instead of waiting for a synchronous response.

### Submit a job

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ocr.extract",
    "input": {
      "file_path": "/path/to/document.png"
    }
  }'
```

### Poll for completion

```bash
curl http://localhost:8000/jobs/{job_id}
```

The response includes `status` (`pending`, `processing`, `completed`, `failed`),
and once completed, the `result` field contains the output.
