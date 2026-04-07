from pydantic import BaseModel, ConfigDict


class UIProviderOption(BaseModel):
    provider: str
    requires_api_key: bool
    supports_byok: bool
    has_env_key: bool


class UIOCRCapability(BaseModel):
    supported_ocr_engines: list[str]
    supported_postprocess_tasks: list[str]


class UIRetrievalCapability(BaseModel):
    supported_retrieval_modes: list[str]
    supports_rerank: bool


class UIRouteMap(BaseModel):
    health: str
    providers: str
    provider_models: str
    runtime_status: str
    jobs_create: str
    jobs_get: str
    ocr_extract: str
    ocr_postprocess: str
    retrieval_index_ocr: str
    retrieval_search: str
    retrieval_hybrid_search: str
    retrieval_rerank: str
    retrieval_qa: str
    pipelines_list: str
    pipelines_run: str
    eval_benchmarks: str
    eval_run: str
    eval_stress: str


class UIConfigResponse(BaseModel):
    app_name: str
    version: str
    providers: list[UIProviderOption]
    ocr: UIOCRCapability
    retrieval: UIRetrievalCapability
    routes: UIRouteMap

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "DocuMind",
                "version": "0.1.0",
                "providers": [
                    {
                        "provider": "ollama",
                        "requires_api_key": False,
                        "supports_byok": False,
                        "has_env_key": False,
                    },
                    {
                        "provider": "openai",
                        "requires_api_key": True,
                        "supports_byok": True,
                        "has_env_key": False,
                    },
                ],
                "ocr": {
                    "supported_ocr_engines": ["deepseek-ocr", "glm-ocr"],
                    "supported_postprocess_tasks": [
                        "cleanup",
                        "summary",
                        "extract_key_fields",
                    ],
                },
                "retrieval": {
                    "supported_retrieval_modes": ["dense", "hybrid"],
                    "supports_rerank": True,
                },
                "routes": {
                    "health": "/health/live",
                    "providers": "/providers",
                    "provider_models": "/providers/{provider}/models",
                    "runtime_status": "/runtime/status",
                    "jobs_create": "/jobs",
                    "jobs_get": "/jobs/{job_id}",
                    "ocr_extract": "/ocr/extract",
                    "ocr_postprocess": "/ocr/postprocess",
                    "retrieval_index_ocr": "/retrieval/index-ocr",
                    "retrieval_search": "/retrieval/search",
                    "retrieval_hybrid_search": "/retrieval/hybrid-search",
                    "retrieval_rerank": "/retrieval/rerank",
                    "retrieval_qa": "/retrieval/qa",
                    "pipelines_list": "/pipelines",
                    "pipelines_run": "/pipelines/run",
                    "eval_benchmarks": "/eval/benchmarks",
                    "eval_run": "/eval/run/{benchmark_name}",
                    "eval_stress": "/eval/stress",
                },
            }
        }
    )


class UIFormField(BaseModel):
    name: str
    type: str
    required: bool
    description: str
    label: str = ""
    placeholder: str = ""


class UIFormDescriptor(BaseModel):
    fields: list[UIFormField]


class UIFormsResponse(BaseModel):
    ocr_extract: UIFormDescriptor
    ocr_postprocess: UIFormDescriptor
    llm_generate: UIFormDescriptor
    retrieval_index_ocr: UIFormDescriptor
    retrieval_qa: UIFormDescriptor
    pipeline_run: UIFormDescriptor
