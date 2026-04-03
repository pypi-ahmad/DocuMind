export type UIFieldType = 'string' | 'boolean' | 'integer' | 'number' | 'object'

export interface UIProviderOption {
  provider: string
  requires_api_key: boolean
  supports_byok: boolean
  has_env_key: boolean
}

export interface UIOCRCapability {
  supported_ocr_engines: string[]
  supported_postprocess_tasks: string[]
}

export interface UIRetrievalCapability {
  supported_retrieval_modes: string[]
  supports_rerank: boolean
}

export interface UIRouteMap {
  health: string
  providers: string
  provider_models: string
  runtime_status: string
  jobs_create: string
  jobs_get: string
  ocr_extract: string
  ocr_postprocess: string
  retrieval_index_ocr: string
  retrieval_search: string
  retrieval_hybrid_search: string
  retrieval_rerank: string
  retrieval_qa: string
  pipelines_list: string
  pipelines_run: string
  eval_benchmarks: string
  eval_run: string
  eval_stress: string
}

export interface UIConfigResponse {
  app_name: string
  version: string
  providers: UIProviderOption[]
  ocr: UIOCRCapability
  retrieval: UIRetrievalCapability
  routes: UIRouteMap
}

export interface UIFormField {
  name: string
  type: UIFieldType
  required: boolean
  description: string
}

export interface UIFormDescriptor {
  fields: UIFormField[]
}

export interface UIFormsResponse {
  ocr_extract: UIFormDescriptor
  ocr_postprocess: UIFormDescriptor
  llm_generate: UIFormDescriptor
  retrieval_index_ocr: UIFormDescriptor
  retrieval_qa: UIFormDescriptor
  pipeline_run: UIFormDescriptor
}

export type ActionKey = keyof UIFormsResponse

export type FormInputValue = string | boolean

export type FormState = Record<string, FormInputValue>

// --- Provider models ---

export interface ModelOption {
  id: string
  display_name: string
  provider: string
}

export interface ProviderModelsResponse {
  provider: string
  models: ModelOption[]
}

export interface PipelineSummary {
  pipeline_name: string
  description: string
}

export interface DocumentSummary {
  doc_id: string
  chunk_count: number
  metadata: Record<string, unknown>
}

// --- Jobs ---

export interface JobResponse {
  job_id: string
  type: string
  status: string
  input: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
}

export type SubmitMode = 'direct' | 'job'

export type WorkflowPresetKey =
  | 'ocr_extract'
  | 'ocr_summary'
  | 'ocr_key_fields'
  | 'ocr_index_document'
  | 'ask_indexed_documents'
  | 'run_named_pipeline'

export type WorkflowStepState = 'pending' | 'running' | 'completed' | 'failed'

export interface WorkflowStepStatus {
  label: string
  status: WorkflowStepState
  detail?: string
}
