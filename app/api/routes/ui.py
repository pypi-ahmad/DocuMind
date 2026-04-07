from fastapi import APIRouter

from app.core.secrets import has_env_api_key
from app.core.settings import settings
from app.ocr.router import VALID_ENGINES
from app.providers.registry import API_KEY_REQUIRED, PROVIDER_FACTORIES
from app.schemas.ocr import POSTPROCESS_TASKS
from app.schemas.ui import (
    UIConfigResponse,
    UIFormDescriptor,
    UIFormField,
    UIFormsResponse,
    UIOCRCapability,
    UIProviderOption,
    UIRetrievalCapability,
    UIRouteMap,
)
from app.services.document_qa import ALLOWED_RETRIEVAL_MODES

router = APIRouter(prefix="/ui", tags=["ui"])


# -- Static route map ----------------------------------------------------------

_ROUTE_MAP = UIRouteMap(
    health="/health/live",
    providers="/providers",
    provider_models="/providers/{provider}/models",
    runtime_status="/runtime/status",
    jobs_create="/jobs",
    jobs_get="/jobs/{job_id}",
    ocr_extract="/ocr/extract",
    ocr_postprocess="/ocr/postprocess",
    retrieval_index_ocr="/retrieval/index-ocr",
    retrieval_search="/retrieval/search",
    retrieval_hybrid_search="/retrieval/hybrid-search",
    retrieval_rerank="/retrieval/rerank",
    retrieval_qa="/retrieval/qa",
    pipelines_list="/pipelines",
    pipelines_run="/pipelines/run",
    eval_benchmarks="/eval/benchmarks",
    eval_run="/eval/run/{benchmark_name}",
    eval_stress="/eval/stress",
)


# -- Static form descriptors ---------------------------------------------------

_FORMS = UIFormsResponse(
    ocr_extract=UIFormDescriptor(
        fields=[
            UIFormField(name="file_path", type="string", required=True, label="Document file", description="Path to the document on the server.", placeholder="e.g. /data/invoices/scan-001.pdf"),
            UIFormField(name="engine", type="string", required=False, label="OCR engine", description="Override the automatic engine selection (leave blank for auto).", placeholder="e.g. deepseek-ocr"),
            UIFormField(name="prefer_structure", type="boolean", required=False, label="Preserve formatting", description="Keep headings, lists, and tables when possible."),
        ]
    ),
    ocr_postprocess=UIFormDescriptor(
        fields=[
            UIFormField(name="ocr_result", type="object", required=True, label="OCR result", description="The OCR result from a previous extraction (JSON)."),
            UIFormField(name="task", type="string", required=True, label="Task", description="What to do with the OCR text: cleanup, summary, or extract_key_fields.", placeholder="e.g. summary"),
            UIFormField(name="provider", type="string", required=True, label="AI provider", description="Which AI provider to use.", placeholder="e.g. ollama, openai"),
            UIFormField(name="model_name", type="string", required=True, label="Model", description="Name of the model to use.", placeholder="e.g. llama3, gpt-4o"),
            UIFormField(name="api_key", type="string", required=False, label="API key", description="Your API key (optional, overrides the server key for this session)."),
            UIFormField(name="temperature", type="number", required=False, label="Creativity", description="Controls randomness (lower = more focused, higher = more creative).", placeholder="e.g. 0.7"),
            UIFormField(name="max_output_tokens", type="integer", required=False, label="Max response length", description="Maximum number of tokens in the response.", placeholder="e.g. 1024"),
        ]
    ),
    llm_generate=UIFormDescriptor(
        fields=[
            UIFormField(name="provider", type="string", required=True, label="AI provider", description="Which AI provider to use.", placeholder="e.g. ollama, openai"),
            UIFormField(name="model_name", type="string", required=True, label="Model", description="Name of the model to use.", placeholder="e.g. llama3, gpt-4o"),
            UIFormField(name="prompt", type="string", required=True, label="Prompt", description="The text prompt to send to the model.", placeholder="e.g. Summarize the following text..."),
            UIFormField(name="api_key", type="string", required=False, label="API key", description="Your API key (optional, overrides the server key for this session)."),
            UIFormField(name="temperature", type="number", required=False, label="Creativity", description="Controls randomness (lower = more focused, higher = more creative).", placeholder="e.g. 0.7"),
            UIFormField(name="max_output_tokens", type="integer", required=False, label="Max response length", description="Maximum number of tokens in the response.", placeholder="e.g. 1024"),
        ]
    ),
    retrieval_index_ocr=UIFormDescriptor(
        fields=[
            UIFormField(name="doc_id", type="string", required=True, label="Document ID", description="A unique name to identify this document.", placeholder="e.g. invoice-2024-001"),
            UIFormField(name="file_path", type="string", required=True, label="Document file", description="Path to the document on the server.", placeholder="e.g. /data/invoices/scan-001.pdf"),
            UIFormField(name="ocr_engine", type="string", required=False, label="OCR engine", description="Override the automatic engine selection (leave blank for auto).", placeholder="e.g. deepseek-ocr"),
            UIFormField(name="prefer_structure", type="boolean", required=False, label="Preserve formatting", description="Keep headings, lists, and tables when possible."),
            UIFormField(name="embedding_provider", type="string", required=True, label="Embedding provider", description="Provider for generating vector embeddings.", placeholder="e.g. ollama, openai"),
            UIFormField(name="embedding_model_name", type="string", required=True, label="Embedding model", description="Name of the embedding model.", placeholder="e.g. nomic-embed-text"),
            UIFormField(name="api_key", type="string", required=False, label="API key", description="Your API key (optional, overrides the server key for this session)."),
            UIFormField(name="metadata", type="object", required=False, label="Metadata", description="Optional extra information to store with the document."),
        ]
    ),
    retrieval_qa=UIFormDescriptor(
        fields=[
            UIFormField(name="query", type="string", required=True, label="Your question", description="What would you like to know from your documents?", placeholder="e.g. What is the total amount due?"),
            UIFormField(name="provider", type="string", required=True, label="AI provider", description="Which AI provider to use for generating the answer.", placeholder="e.g. ollama, openai"),
            UIFormField(name="model_name", type="string", required=True, label="Model", description="Name of the model for generating answers.", placeholder="e.g. llama3, gpt-4o"),
            UIFormField(name="api_key", type="string", required=False, label="API key", description="Your API key (optional, overrides the server key for this session)."),
            UIFormField(name="retrieval_mode", type="string", required=False, label="Search method", description="How to search your documents: dense (vector) or hybrid (vector + keyword).", placeholder="e.g. hybrid"),
            UIFormField(name="top_k", type="integer", required=False, label="Number of results", description="How many search results to consider.", placeholder="e.g. 5"),
            UIFormField(name="use_rerank", type="boolean", required=False, label="Re-rank results", description="Re-score results for better relevance before answering."),
            UIFormField(name="rerank_top_k", type="integer", required=False, label="Keep top N after re-ranking", description="How many top results to keep after re-ranking.", placeholder="e.g. 3"),
            UIFormField(name="temperature", type="number", required=False, label="Creativity", description="Controls randomness (lower = more focused, higher = more creative).", placeholder="e.g. 0.7"),
            UIFormField(name="max_output_tokens", type="integer", required=False, label="Max response length", description="Maximum number of tokens in the response.", placeholder="e.g. 1024"),
        ]
    ),
    pipeline_run=UIFormDescriptor(
        fields=[
            UIFormField(name="pipeline_name", type="string", required=True, label="Pipeline name", description="Name of the pipeline to execute.", placeholder="e.g. ocr_extract_then_summary"),
            UIFormField(name="input", type="object", required=True, label="Pipeline input", description="Input data for the pipeline (JSON)."),
        ]
    ),
)


@router.get(
    "/config",
    response_model=UIConfigResponse,
    summary="Get UI configuration",
    description="Return frontend-safe capability metadata including providers, OCR, retrieval, and route paths.",
)
def get_ui_config() -> UIConfigResponse:
    providers = [
        UIProviderOption(
            provider=name,
            requires_api_key=name in API_KEY_REQUIRED,
            supports_byok=name in API_KEY_REQUIRED,
            has_env_key=has_env_api_key(name),
        )
        for name in PROVIDER_FACTORIES
    ]

    supported_retrieval_modes = [mode for mode in ("dense", "hybrid") if mode in ALLOWED_RETRIEVAL_MODES]
    supported_postprocess_tasks = [
        task for task in ("cleanup", "summary", "extract_key_fields") if task in POSTPROCESS_TASKS
    ]

    return UIConfigResponse(
        app_name=settings.app_name,
        version=settings.version,
        providers=providers,
        ocr=UIOCRCapability(
            supported_ocr_engines=sorted(VALID_ENGINES),
            supported_postprocess_tasks=supported_postprocess_tasks,
        ),
        retrieval=UIRetrievalCapability(
            supported_retrieval_modes=supported_retrieval_modes,
            supports_rerank=True,
        ),
        routes=_ROUTE_MAP,
    )


@router.get(
    "/forms",
    response_model=UIFormsResponse,
    summary="Get UI form descriptors",
    description="Return field-level metadata for key request forms so a frontend can render inputs without guessing.",
)
def get_ui_forms() -> UIFormsResponse:
    return _FORMS
