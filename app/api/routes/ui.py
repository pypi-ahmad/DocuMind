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
            UIFormField(name="file_path", type="string", required=True, description="Path to the document file."),
            UIFormField(name="engine", type="string", required=False, description="OCR engine override (optional)."),
            UIFormField(name="prefer_structure", type="boolean", required=False, description="Prefer structured output."),
        ]
    ),
    ocr_postprocess=UIFormDescriptor(
        fields=[
            UIFormField(name="ocr_result", type="object", required=True, description="OCR extraction result dict."),
            UIFormField(name="task", type="string", required=True, description="Post-process task: cleanup, summary, or extract_key_fields."),
            UIFormField(name="provider", type="string", required=True, description="LLM provider name."),
            UIFormField(name="model_name", type="string", required=True, description="Model name for post-processing."),
            UIFormField(name="api_key", type="string", required=False, description="BYOK API key (optional)."),
            UIFormField(name="temperature", type="number", required=False, description="Sampling temperature."),
            UIFormField(name="max_output_tokens", type="integer", required=False, description="Maximum output tokens."),
        ]
    ),
    llm_generate=UIFormDescriptor(
        fields=[
            UIFormField(name="provider", type="string", required=True, description="LLM provider name."),
            UIFormField(name="model_name", type="string", required=True, description="Model name to use."),
            UIFormField(name="prompt", type="string", required=True, description="Text prompt for generation."),
            UIFormField(name="api_key", type="string", required=False, description="BYOK API key (optional)."),
            UIFormField(name="temperature", type="number", required=False, description="Sampling temperature."),
            UIFormField(name="max_output_tokens", type="integer", required=False, description="Maximum output tokens."),
        ]
    ),
    retrieval_index_ocr=UIFormDescriptor(
        fields=[
            UIFormField(name="doc_id", type="string", required=True, description="Unique document identifier."),
            UIFormField(name="file_path", type="string", required=True, description="Path to the document file."),
            UIFormField(name="ocr_engine", type="string", required=False, description="OCR engine override (optional)."),
            UIFormField(name="prefer_structure", type="boolean", required=False, description="Prefer structured OCR output."),
            UIFormField(name="embedding_provider", type="string", required=True, description="Embedding provider name."),
            UIFormField(name="embedding_model_name", type="string", required=True, description="Embedding model name."),
            UIFormField(name="api_key", type="string", required=False, description="BYOK API key (optional)."),
            UIFormField(name="metadata", type="object", required=False, description="Optional document metadata."),
        ]
    ),
    retrieval_qa=UIFormDescriptor(
        fields=[
            UIFormField(name="query", type="string", required=True, description="Question to answer from indexed documents."),
            UIFormField(name="provider", type="string", required=True, description="LLM provider name."),
            UIFormField(name="model_name", type="string", required=True, description="Model name for generation."),
            UIFormField(name="api_key", type="string", required=False, description="BYOK API key (optional)."),
            UIFormField(name="retrieval_mode", type="string", required=False, description="Retrieval mode: dense or hybrid."),
            UIFormField(name="top_k", type="integer", required=False, description="Number of retrieval results."),
            UIFormField(name="use_rerank", type="boolean", required=False, description="Enable reranking of results."),
            UIFormField(name="rerank_top_k", type="integer", required=False, description="Number of results after reranking."),
            UIFormField(name="temperature", type="number", required=False, description="Sampling temperature."),
            UIFormField(name="max_output_tokens", type="integer", required=False, description="Maximum output tokens."),
        ]
    ),
    pipeline_run=UIFormDescriptor(
        fields=[
            UIFormField(name="pipeline_name", type="string", required=True, description="Name of the pipeline to execute."),
            UIFormField(name="input", type="object", required=True, description="Pipeline input payload."),
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
