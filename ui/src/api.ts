import type {
  ActionKey,
  DocumentSummary,
  JobResponse,
  PipelineSummary,
  ProviderModelsResponse,
  UIConfigResponse,
  UIFormsResponse,
} from './types'

const DEFAULT_API_BASE_URL = 'http://localhost:8000'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL

export const ACTION_ENDPOINTS: Record<ActionKey, string> = {
  ocr_extract: '/ocr/extract',
  ocr_postprocess: '/ocr/postprocess',
  llm_generate: '/llm/generate',
  retrieval_index_ocr: '/retrieval/index-ocr',
  retrieval_qa: '/retrieval/qa',
  pipeline_run: '/pipelines/run',
}

export const ACTION_JOB_TYPES: Partial<Record<ActionKey, string>> = {
  ocr_extract: 'ocr.extract',
  ocr_postprocess: 'ocr.postprocess',
  retrieval_index_ocr: 'retrieval.index_ocr',
  retrieval_qa: 'retrieval.qa',
  pipeline_run: 'pipeline.run',
}

function getErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
  }

  return `Request failed with status ${status}`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  const text = await response.text()
  let data: unknown = null

  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error('Backend returned a non-JSON response')
    }
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(data, response.status))
  }

  return data as T
}

export async function loadUiConfig(): Promise<UIConfigResponse> {
  return requestJson<UIConfigResponse>('/ui/config')
}

export async function loadUiForms(): Promise<UIFormsResponse> {
  return requestJson<UIFormsResponse>('/ui/forms')
}

export async function submitAction(action: ActionKey, payload: unknown): Promise<unknown> {
  return requestJson(ACTION_ENDPOINTS[action], {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchProviderModels(provider: string, apiKey?: string): Promise<ProviderModelsResponse> {
  const body = apiKey ? { api_key: apiKey } : undefined
  return requestJson<ProviderModelsResponse>(`/providers/${encodeURIComponent(provider)}/models`, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

export async function submitJob(jobType: string, input: Record<string, unknown>): Promise<JobResponse> {
  return requestJson<JobResponse>('/jobs', {
    method: 'POST',
    body: JSON.stringify({ type: jobType, input }),
  })
}

export async function fetchJob(jobId: string): Promise<JobResponse> {
  return requestJson<JobResponse>(`/jobs/${encodeURIComponent(jobId)}`)
}

export async function fetchPipelines(): Promise<PipelineSummary[]> {
  return requestJson<PipelineSummary[]>('/pipelines')
}

export async function fetchIndexedDocuments(): Promise<DocumentSummary[]> {
  return requestJson<DocumentSummary[]>('/retrieval/documents')
}

export async function uploadDocument(file: File): Promise<{ file_path: string }> {
  const body = new FormData()
  body.append('file', file)

  const response = await fetch(`${API_BASE_URL}/ocr/upload`, {
    method: 'POST',
    body,
  })

  const text = await response.text()
  let data: unknown = null

  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error('Backend returned a non-JSON response')
    }
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(data, response.status))
  }

  return data as { file_path: string }
}
