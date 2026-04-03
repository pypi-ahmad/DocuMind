# DocuMind UI

React + TypeScript + Vite frontend for the DocuMind document intelligence
platform.

---

## What the UI Does

The UI provides a browser-based interface for all DocuMind backend capabilities:

- Discovers backend capabilities at startup via `GET /ui/config` and
  `GET /ui/forms`.
- Renders forms dynamically from backend field metadata for supported actions,
  so the UI does not maintain separate hand-built field definitions per action.
- Offers **Workflow Presets** for common flows (OCR extract, OCR + summary,
  retrieval QA, etc.) that guide users through the right fields and steps.
- Falls back to a **Generic Action Form** for full manual control over any
  backend action.
- Displays provider metadata, OCR engine lists, and retrieval mode information
  from the backend contract.

---

## Backend Requirement

Start the FastAPI backend before running the UI:

```bash
# From the project root
uvicorn app.main:app --reload
```

The frontend expects these backend endpoints:

- `GET /ui/config` — capability discovery
- `GET /ui/forms` — form field metadata
- `POST /providers/{provider}/models` — model listing
- `POST /jobs` / `GET /jobs/{job_id}` — background job support
- All action endpoints (`/ocr/extract`, `/retrieval/qa`, etc.)

---

## BYOK (Bring Your Own Key)

For cloud providers (`openai`, `gemini`, `anthropic`) the UI shows an optional
API key input when one of those providers is selected.

- If a key is entered, it is sent with the request and overrides the server's
  `.env` fallback.
- If the field is left blank, the backend uses its configured `.env` key (if
  any).
- **Keys are held only in React component state.** They are never written to
  `localStorage`, `sessionStorage`, cookies, URLs, or backend storage.

---

## Model Dropdown

When a provider is selected, the UI calls
`POST /providers/{provider}/models` (including the BYOK key if entered). The
returned models populate a dropdown. If the call fails (missing key, network
error), the dropdown falls back to a manual text input.

The OCR Index Document preset reuses this selector for embedding provider and
model fields.

---

## Direct vs Job Mode

Actions that support a backend job type offer a **Submit mode** toggle:

| Action | Job type |
|--------|----------|
| `ocr_extract` | `ocr.extract` |
| `ocr_postprocess` | `ocr.postprocess` |
| `retrieval_index_ocr` | `retrieval.index_ocr` |
| `retrieval_qa` | `retrieval.qa` |
| `pipeline_run` | `pipeline.run` |

- **Direct** — the request goes to the action endpoint and blocks until done.
- **Job** — the request goes to `POST /jobs`, then the UI polls
  `GET /jobs/{job_id}` every 2 seconds until `completed` or `failed`.

`llm_generate` is direct-only.

---

## Workflow Presets

| Preset | Backend mapping | Flow |
|--------|-----------------|------|
| OCR Extract | `POST /ocr/extract` | Single step |
| OCR + Summary | `/ocr/extract` → `/ocr/postprocess` (task=summary) | Multi-step |
| OCR + Key Fields | `/ocr/extract` → `/ocr/postprocess` (task=extract_key_fields) | Multi-step |
| OCR Index Document | `POST /retrieval/index-ocr` | Single step |
| Ask Indexed Documents | `POST /retrieval/qa` + `GET /retrieval/documents` | Single step |
| Run Named Pipeline | `GET /pipelines` + `POST /pipelines/run` | Single step |

Multi-step presets run OCR extraction first and only proceed to the next step if
OCR succeeds. Intermediate results and step-by-step progress are shown in the UI.

Clicking **"Use Generic Form Mode"** exits the preset layer and returns to the
action dropdown.

---

## Development

### Install

```bash
cd ui
npm install
```

### Run (dev server)

```bash
npm run dev
```

Starts on `http://localhost:5173`. Set the backend URL if needed:

```bash
# PowerShell
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

### Type check

```bash
npx tsc --noEmit
```

### Build

```bash
npm run build
```

Output goes to `ui/dist/`.

---

## Project Structure

```
ui/
├── src/
│   ├── App.tsx                     # Main component, state, orchestration
│   ├── api.ts                      # Typed API client functions
│   ├── types.ts                    # Shared TypeScript type definitions
│   ├── main.tsx                    # React entry point
│   ├── styles.css                  # All styles
│   └── components/
│       ├── DynamicForm.tsx         # Dynamic form from backend descriptors
│       ├── ProviderModelSelector.tsx # Provider/model/BYOK selector
│       ├── JobPoller.tsx           # Background job polling display
│       ├── JsonBlock.tsx           # JSON pretty-print block
│       ├── WorkflowPresetCards.tsx # Preset card grid
│       ├── WorkflowStatus.tsx      # Multi-step progress display
│       ├── PipelineSelector.tsx    # Pipeline name dropdown
│       └── IndexedDocumentsList.tsx # Indexed document summary list
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```
