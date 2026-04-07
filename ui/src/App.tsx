import { type FormEvent, useEffect, useMemo, useState } from 'react'

import {
  ACTION_ENDPOINTS,
  ACTION_JOB_TYPES,
  API_BASE_URL,
  fetchIndexedDocuments,
  fetchPipelines,
  loadUiConfig,
  loadUiForms,
  submitAction,
  submitJob,
} from './api'
import { DynamicForm } from './components/DynamicForm'
import { FileUpload } from './components/FileUpload'
import { IndexedDocumentsList } from './components/IndexedDocumentsList'
import { FormattedResult } from './components/FormattedResult'
import { JobPoller } from './components/JobPoller'
import { JsonBlock } from './components/JsonBlock'
import { PipelineSelector } from './components/PipelineSelector'
import { ProviderModelSelector } from './components/ProviderModelSelector'
import { WorkflowPresetCards } from './components/WorkflowPresetCards'
import { WorkflowStatus } from './components/WorkflowStatus'
import type {
  ActionKey,
  DocumentSummary,
  FormState,
  JobResponse,
  PipelineSummary,
  SubmitMode,
  UIConfigResponse,
  UIFormDescriptor,
  UIFormField,
  UIFormsResponse,
  WorkflowPresetKey,
  WorkflowStepStatus,
} from './types'

const ACTION_LABELS: Record<ActionKey, string> = {
  ocr_extract: 'Extract Text (OCR)',
  ocr_postprocess: 'Post-process Document',
  llm_generate: 'Generate Text',
  retrieval_index_ocr: 'Index Document',
  retrieval_qa: 'Question & Answer',
  pipeline_run: 'Run Pipeline',
}

const PROVIDER_ACTIONS = new Set<ActionKey>(['ocr_postprocess', 'llm_generate', 'retrieval_qa'])
const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed'])
const CLOUD_PROVIDERS = new Set(['openai', 'gemini', 'anthropic'])
const GENERIC_SELECTOR_FIELDS = new Set(['provider', 'model_name', 'api_key'])

const PRESET_TO_ACTION: Record<WorkflowPresetKey, ActionKey> = {
  ocr_extract: 'ocr_extract',
  ocr_summary: 'ocr_postprocess',
  ocr_key_fields: 'ocr_postprocess',
  ocr_index_document: 'retrieval_index_ocr',
  ask_indexed_documents: 'retrieval_qa',
  run_named_pipeline: 'pipeline_run',
}

const PRESET_OPTIONS: Array<{
  key: WorkflowPresetKey
  title: string
  description: string
  flowLabel: string
}> = [
  {
    key: 'ocr_extract',
    title: 'Extract Text',
    description: 'Extract text from an image or PDF.',
    flowLabel: 'Single step',
  },
  {
    key: 'ocr_summary',
    title: 'Extract & Summarize',
    description: 'Extract text and generate a summary.',
    flowLabel: 'Multi step',
  },
  {
    key: 'ocr_key_fields',
    title: 'Extract Key Fields',
    description: 'Extract text and identify key fields like dates, names, and amounts.',
    flowLabel: 'Multi step',
  },
  {
    key: 'ocr_index_document',
    title: 'Index Document',
    description: 'Extract text and save it for later search and Q&A.',
    flowLabel: 'Single step',
  },
  {
    key: 'ask_indexed_documents',
    title: 'Ask Your Documents',
    description: 'Ask questions about your saved documents.',
    flowLabel: 'Single step',
  },
  {
    key: 'run_named_pipeline',
    title: 'Run Pipeline',
    description: 'Run a pre-configured multi-step workflow.',
    flowLabel: 'Single step',
  },
]

const PRESET_DEFAULTS: Record<WorkflowPresetKey, FormState> = {
  ocr_extract: {
    prefer_structure: 'false',
  },
  ocr_summary: {
    prefer_structure: 'false',
  },
  ocr_key_fields: {
    prefer_structure: 'false',
  },
  ocr_index_document: {
    prefer_structure: 'true',
  },
  ask_indexed_documents: {
    retrieval_mode: 'hybrid',
    use_rerank: 'true',
  },
  run_named_pipeline: {
    input: '{}',
  },
}

function parseFieldValue(field: UIFormField, rawValue: string | boolean | undefined): unknown {
  if (field.type === 'boolean') {
    if (rawValue === '') {
      return undefined
    }

    return rawValue === 'true'
  }

  if (typeof rawValue !== 'string') {
    return undefined
  }

  const trimmed = rawValue.trim()
  if (!trimmed) {
    return undefined
  }

  if (field.type === 'integer') {
    const parsed = Number.parseInt(trimmed, 10)
    if (Number.isNaN(parsed)) {
      throw new Error(`${humanFieldName(field.name)} must be a valid integer`)
    }

    return parsed
  }

  if (field.type === 'number') {
    const parsed = Number(trimmed)
    if (Number.isNaN(parsed)) {
      throw new Error(`${humanFieldName(field.name)} must be a valid number`)
    }

    return parsed
  }

  if (field.type === 'object') {
    try {
      return JSON.parse(trimmed)
    } catch {
      throw new Error(`${humanFieldName(field.name)} must be valid JSON`)
    }
  }

  return trimmed
}

function buildPayload(fields: UIFormField[], values: FormState): Record<string, unknown> {
  return fields.reduce<Record<string, unknown>>((payload, field) => {
    const parsedValue = parseFieldValue(field, values[field.name])

    if (parsedValue === undefined) {
      if (field.required) {
        throw new Error(`${humanFieldName(field.name)} is required`)
      }

      return payload
    }

    payload[field.name] = parsedValue
    return payload
  }, {})
}

function pickDescriptorFields(descriptor: UIFormDescriptor, fieldNames: string[]): UIFormDescriptor {
  return {
    fields: fieldNames.flatMap((fieldName) => {
      const field = descriptor.fields.find((candidate) => candidate.name === fieldName)
      return field ? [field] : []
    }),
  }
}

function getPresetDescriptor(forms: UIFormsResponse, preset: WorkflowPresetKey): UIFormDescriptor {
  switch (preset) {
    case 'ocr_extract':
      return pickDescriptorFields(forms.ocr_extract, ['file_path', 'engine', 'prefer_structure'])
    case 'ocr_summary':
    case 'ocr_key_fields':
      return pickDescriptorFields(forms.ocr_extract, ['file_path', 'engine', 'prefer_structure'])
    case 'ocr_index_document':
      return pickDescriptorFields(forms.retrieval_index_ocr, [
        'doc_id',
        'file_path',
        'ocr_engine',
        'prefer_structure',
        'metadata',
      ])
    case 'ask_indexed_documents':
      return pickDescriptorFields(forms.retrieval_qa, [
        'query',
        'retrieval_mode',
        'top_k',
        'use_rerank',
        'rerank_top_k',
      ])
    case 'run_named_pipeline':
      return pickDescriptorFields(forms.pipeline_run, ['input'])
  }
}

function redactPreviewSecrets(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(redactPreviewSecrets)
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, entryValue]) => {
        if (key === 'api_key') {
          return [key, '[redacted]']
        }

        return [key, redactPreviewSecrets(entryValue)]
      }),
    )
  }

  return value
}

function humanFieldName(raw: string): string {
  const map: Record<string, string> = {
    provider: 'Provider',
    model_name: 'Model',
    api_key: 'API key',
    pipeline_name: 'Pipeline',
    file_path: 'Document file',
    query: 'Question',
    doc_id: 'Document ID',
    top_k: 'Number of results',
    temperature: 'Creativity',
    max_output_tokens: 'Max response length',
    prefer_structure: 'Preserve formatting',
    use_rerank: 'Re-rank results',
    rerank_top_k: 'Re-rank to top N',
    retrieval_mode: 'Search method',
    ocr_engine: 'OCR engine',
    metadata: 'Metadata',
    input: 'Pipeline input',
  }
  return map[raw] ?? raw.replace(/_/g, ' ')
}

function shouldTreatAsFieldError(message: string): boolean {
  return (
    message.includes('valid JSON') ||
    message.includes('required') ||
    message.includes('valid integer') ||
    message.includes('valid number')
  )
}

export default function App() {
  const [config, setConfig] = useState<UIConfigResponse | null>(null)
  const [forms, setForms] = useState<UIFormsResponse | null>(null)
  const [selectedAction, setSelectedAction] = useState<ActionKey>('ocr_extract')
  const [selectedPreset, setSelectedPreset] = useState<WorkflowPresetKey | null>(null)
  const [formValues, setFormValues] = useState<FormState>({})
  const [loadError, setLoadError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [responseData, setResponseData] = useState<unknown>(null)
  const [requestPreview, setRequestPreview] = useState<unknown>(null)
  const [intermediateResult, setIntermediateResult] = useState<unknown>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState('')
  const [selectedModel, setSelectedModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [submitMode, setSubmitMode] = useState<SubmitMode>('direct')
  const [submittedJob, setSubmittedJob] = useState<JobResponse | null>(null)
  const [jobSnapshot, setJobSnapshot] = useState<JobResponse | null>(null)
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStepStatus[]>([])
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([])
  const [isLoadingPipelines, setIsLoadingPipelines] = useState(false)
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [selectedPipelineName, setSelectedPipelineName] = useState('')
  const [indexedDocuments, setIndexedDocuments] = useState<DocumentSummary[]>([])
  const [isLoadingIndexedDocuments, setIsLoadingIndexedDocuments] = useState(false)
  const [indexedDocumentsError, setIndexedDocumentsError] = useState<string | null>(null)

  const currentAction = selectedPreset ? PRESET_TO_ACTION[selectedPreset] : selectedAction
  const activePreset = selectedPreset ? PRESET_OPTIONS.find((preset) => preset.key === selectedPreset) ?? null : null
  const activeJob = jobSnapshot ?? submittedJob
  const isJobPolling = Boolean(activeJob && !TERMINAL_JOB_STATUSES.has(activeJob.status))
  const isActionBusy = isSubmitting || isJobPolling

  const usesLlmSelector =
    (!selectedPreset && PROVIDER_ACTIONS.has(currentAction)) ||
    selectedPreset === 'ocr_summary' ||
    selectedPreset === 'ocr_key_fields' ||
    selectedPreset === 'ask_indexed_documents'

  const usesEmbeddingSelector = selectedPreset === 'ocr_index_document'
  const usesPipelineSelector = selectedPreset === 'run_named_pipeline'

  const selectorConfig = useMemo(() => {
    if (usesEmbeddingSelector) {
      return {
        providerFieldName: 'embedding_provider',
        modelFieldName: 'embedding_model_name',
        apiKeyFieldName: 'api_key',
        providerLabel: 'Embedding Provider',
        modelLabel: 'Embedding Model',
      }
    }

    if (usesLlmSelector) {
      return {
        providerFieldName: 'provider',
        modelFieldName: 'model_name',
        apiKeyFieldName: 'api_key',
        providerLabel: 'Provider',
        modelLabel: 'Model',
      }
    }

    return null
  }, [usesEmbeddingSelector, usesLlmSelector])

  const currentDescriptor = useMemo(() => {
    if (!forms) {
      return null
    }

    if (selectedPreset) {
      return getPresetDescriptor(forms, selectedPreset)
    }

    return forms[currentAction]
  }, [forms, currentAction, selectedPreset])

  const visibleFields = useMemo(() => {
    if (!currentDescriptor) {
      return []
    }

    if (!selectedPreset && usesLlmSelector) {
      return currentDescriptor.fields.filter((field) => !GENERIC_SELECTOR_FIELDS.has(field.name))
    }

    return currentDescriptor.fields
  }, [currentDescriptor, selectedPreset, usesLlmSelector])

  const supportsJobMode = useMemo(() => {
    if (selectedPreset === 'ocr_extract') {
      return false
    }

    return currentAction in ACTION_JOB_TYPES
  }, [currentAction, selectedPreset])

  function resetExecutionState() {
    setFieldError(null)
    setSubmitError(null)
    setResponseData(null)
    setRequestPreview(null)
    setIntermediateResult(null)
    setSubmittedJob(null)
    setJobSnapshot(null)
    setWorkflowSteps([])
  }

  function handleSubmissionError(error: unknown) {
    const message = error instanceof Error ? error.message : 'Submission failed'

    if (shouldTreatAsFieldError(message)) {
      setFieldError(message)
      return
    }

    setSubmitError(message)
  }

  function includeApiKeyForProvider(providerName: string): boolean {
    if (!config) {
      return false
    }

    const provider = config.providers.find((candidate) => candidate.provider === providerName)
    return Boolean(provider?.supports_byok && apiKey.trim())
  }

  function buildCurrentPayload(): Record<string, unknown> {
    const payload = buildPayload(visibleFields, formValues)

    if (selectorConfig) {
      if (!selectedProvider) {
        throw new Error(`${humanFieldName(selectorConfig.providerFieldName)} is required`)
      }

      if (!selectedModel) {
        throw new Error(`${humanFieldName(selectorConfig.modelFieldName)} is required`)
      }

      payload[selectorConfig.providerFieldName] = selectedProvider
      payload[selectorConfig.modelFieldName] = selectedModel

      if (includeApiKeyForProvider(selectedProvider)) {
        payload[selectorConfig.apiKeyFieldName] = apiKey.trim()
      }
    }

    if (usesPipelineSelector) {
      if (!selectedPipelineName.trim()) {
        throw new Error('Pipeline is required')
      }

      payload.pipeline_name = selectedPipelineName.trim()
    }

    return payload
  }

  function updateLastWorkflowStep(status: WorkflowStepStatus['status'], detail?: string) {
    setWorkflowSteps((current) => {
      if (current.length === 0) {
        return current
      }

      return current.map((step, index) =>
        index === current.length - 1
          ? {
              ...step,
              status,
              detail,
            }
          : step,
      )
    })
  }

  function handleJobUpdate(job: JobResponse) {
    setJobSnapshot(job)

    if (!selectedPreset) {
      return
    }

    if (job.status === 'completed') {
      updateLastWorkflowStep('completed', `Job ${job.job_id} completed.`)
      return
    }

    if (job.status === 'failed') {
      updateLastWorkflowStep('failed', job.error ?? `Job ${job.job_id} failed.`)
      return
    }

    updateLastWorkflowStep('running', `Job ${job.job_id} is ${job.status}.`)
  }

  async function runMultiStepOcrWorkflow(task: 'summary' | 'extract_key_fields') {
    const workflowLabel = task === 'summary' ? 'Generate summary' : 'Extract key fields'
    const extractPayload = buildPayload(visibleFields, formValues)

    if (!selectedProvider) {
      throw new Error('Provider is required')
    }

    if (!selectedModel) {
      throw new Error('Model is required')
    }

    const baseStepTwoPayload: Record<string, unknown> = {
      task,
      provider: selectedProvider,
      model_name: selectedModel,
    }

    if (includeApiKeyForProvider(selectedProvider)) {
      baseStepTwoPayload.api_key = apiKey.trim()
    }

    setWorkflowSteps([
      { label: 'Step 1: Extract text', status: 'running' },
      { label: `Step 2: ${workflowLabel}`, status: 'pending' },
    ])

    setRequestPreview(
      redactPreviewSecrets({
        step_1: {
          endpoint: ACTION_ENDPOINTS.ocr_extract,
          payload: extractPayload,
        },
        step_2:
          submitMode === 'job'
            ? {
                endpoint: '/jobs',
                body: {
                  type: ACTION_JOB_TYPES.ocr_postprocess,
                  input: {
                    ...baseStepTwoPayload,
                    ocr_result: '<see intermediate OCR result>',
                  },
                },
              }
            : {
                endpoint: ACTION_ENDPOINTS.ocr_postprocess,
                payload: {
                  ...baseStepTwoPayload,
                  ocr_result: '<see intermediate OCR result>',
                },
              },
      }),
    )

    let currentStep: 1 | 2 = 1
    setIsSubmitting(true)

    try {
      const ocrResponse = await submitAction('ocr_extract', extractPayload)
      setIntermediateResult(ocrResponse)
      currentStep = 2
      setWorkflowSteps([
        { label: 'Step 1: OCR extract', status: 'completed' },
        { label: `Step 2: ${workflowLabel}`, status: 'running' },
      ])

      const stepTwoPayload = {
        ...baseStepTwoPayload,
        ocr_result: ocrResponse,
      }

      if (submitMode === 'job' && supportsJobMode) {
        const jobType = ACTION_JOB_TYPES.ocr_postprocess
        if (!jobType) {
          throw new Error('Job mode is not available for this workflow')
        }

        const jobResponse = await submitJob(jobType, stepTwoPayload)
        setSubmittedJob(jobResponse)
        setJobSnapshot(null)
        setWorkflowSteps([
          { label: 'Step 1: OCR extract', status: 'completed' },
          {
            label: `Step 2: ${workflowLabel}`,
            status: 'running',
            detail: `Job ${jobResponse.job_id} submitted. Polling for completion.`,
          },
        ])
        return
      }

      const nextResponse = await submitAction('ocr_postprocess', stepTwoPayload)
      setResponseData(nextResponse)
      setWorkflowSteps([
        { label: 'Step 1: OCR extract', status: 'completed' },
        { label: `Step 2: ${workflowLabel}`, status: 'completed' },
      ])
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Workflow failed'
      if (currentStep === 1) {
        setWorkflowSteps([
          { label: 'Step 1: OCR extract', status: 'failed', detail: message },
          { label: `Step 2: ${workflowLabel}`, status: 'pending' },
        ])
      } else {
        setWorkflowSteps([
          { label: 'Step 1: OCR extract', status: 'completed' },
          { label: `Step 2: ${workflowLabel}`, status: 'failed', detail: message },
        ])
      }
      throw error
    } finally {
      setIsSubmitting(false)
    }
  }

  async function runSingleStepFlow() {
    const payload = buildCurrentPayload()
    const previewValue =
      submitMode === 'job' && supportsJobMode
        ? {
            type: ACTION_JOB_TYPES[currentAction],
            input: payload,
          }
        : payload

    setRequestPreview(redactPreviewSecrets(previewValue))

    if (selectedPreset) {
      setWorkflowSteps([
        {
          label: activePreset?.title ?? ACTION_LABELS[currentAction],
          status: 'running',
        },
      ])
    }

    setIsSubmitting(true)

    try {
      if (submitMode === 'job' && supportsJobMode) {
        const jobType = ACTION_JOB_TYPES[currentAction]
        if (!jobType) {
          throw new Error('Job mode is not available for this action')
        }

        const jobResponse = await submitJob(jobType, payload)
        setSubmittedJob(jobResponse)
        setJobSnapshot(null)

        if (selectedPreset) {
          setWorkflowSteps([
            {
              label: activePreset?.title ?? ACTION_LABELS[currentAction],
              status: 'running',
              detail: `Job ${jobResponse.job_id} submitted. Polling for completion.`,
            },
          ])
        }

        return
      }

      const nextResponse = await submitAction(currentAction, payload)
      setResponseData(nextResponse)

      if (selectedPreset) {
        setWorkflowSteps([
          {
            label: activePreset?.title ?? ACTION_LABELS[currentAction],
            status: 'completed',
          },
        ])
      }
    } catch (error) {
      if (selectedPreset) {
        const message = error instanceof Error ? error.message : 'Workflow failed'
        setWorkflowSteps([
          {
            label: activePreset?.title ?? ACTION_LABELS[currentAction],
            status: 'failed',
            detail: message,
          },
        ])
      }

      throw error
    } finally {
      setIsSubmitting(false)
    }
  }

  useEffect(() => {
    let isMounted = true

    async function hydrate() {
      setIsLoading(true)
      setLoadError(null)

      try {
        const [nextConfig, nextForms] = await Promise.all([loadUiConfig(), loadUiForms()])
        if (!isMounted) {
          return
        }

        setConfig(nextConfig)
        setForms(nextForms)

        if (nextConfig.providers.length > 0) {
          setSelectedProvider(nextConfig.providers[0].provider)
        }
      } catch (error) {
        if (!isMounted) {
          return
        }

        setLoadError(error instanceof Error ? error.message : 'Could not connect to the DocuMind server')
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    void hydrate()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (selectedPreset !== null) {
      return
    }

    setFormValues({})
    setSubmitMode('direct')
    resetExecutionState()
  }, [selectedAction, selectedPreset])

  useEffect(() => {
    resetExecutionState()
    setSubmitMode('direct')
    setPipelines([])
    setIsLoadingPipelines(false)
    setPipelineError(null)
    setSelectedPipelineName('')
    setIndexedDocuments([])
    setIsLoadingIndexedDocuments(false)
    setIndexedDocumentsError(null)

    if (selectedPreset) {
      setFormValues(PRESET_DEFAULTS[selectedPreset])
      return
    }

    setFormValues({})
  }, [selectedPreset])

  useEffect(() => {
    if (selectedPreset !== 'run_named_pipeline') {
      return
    }

    let cancelled = false

    async function loadPipelineOptions() {
      setIsLoadingPipelines(true)
      setPipelineError(null)

      try {
        const nextPipelines = await fetchPipelines()
        if (cancelled) {
          return
        }

        setPipelines(nextPipelines)
        if (nextPipelines.length > 0) {
          setSelectedPipelineName(nextPipelines[0].pipeline_name)
        }
      } catch (error) {
        if (cancelled) {
          return
        }

        setPipelines([])
        setPipelineError(error instanceof Error ? error.message : 'Unable to load pipelines')
      } finally {
        if (!cancelled) {
          setIsLoadingPipelines(false)
        }
      }
    }

    void loadPipelineOptions()

    return () => {
      cancelled = true
    }
  }, [selectedPreset])

  useEffect(() => {
    if (selectedPreset !== 'ask_indexed_documents') {
      return
    }

    let cancelled = false

    async function loadDocumentSummaries() {
      setIsLoadingIndexedDocuments(true)
      setIndexedDocumentsError(null)

      try {
        const nextDocuments = await fetchIndexedDocuments()
        if (cancelled) {
          return
        }

        setIndexedDocuments(nextDocuments)
      } catch (error) {
        if (cancelled) {
          return
        }

        setIndexedDocuments([])
        setIndexedDocumentsError(error instanceof Error ? error.message : 'Unable to load indexed documents')
      } finally {
        if (!cancelled) {
          setIsLoadingIndexedDocuments(false)
        }
      }
    }

    void loadDocumentSummaries()

    return () => {
      cancelled = true
    }
  }, [selectedPreset])

  function handleFieldChange(fieldName: string, value: string | boolean) {
    setFormValues((current) => ({
      ...current,
      [fieldName]: value,
    }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!forms || !currentDescriptor) {
      return
    }

    resetExecutionState()

    try {
      if (selectedPreset === 'ocr_summary') {
        await runMultiStepOcrWorkflow('summary')
        return
      }

      if (selectedPreset === 'ocr_key_fields') {
        await runMultiStepOcrWorkflow('extract_key_fields')
        return
      }

      await runSingleStepFlow()
    } catch (error) {
      handleSubmissionError(error)
    }
  }

  if (isLoading) {
    return (
      <main className="app-shell">
        <p className="message info">Connecting to DocuMind…</p>
      </main>
    )
  }

  if (loadError || !config || !forms || !currentDescriptor) {
    return (
      <main className="app-shell">
        <p className="message error">{loadError ?? 'Could not connect to the DocuMind server.'}</p>
        <p className="field-help">Make sure the server is running and refresh the page. Backend URL: {API_BASE_URL}</p>
      </main>
    )
  }

  const activeError = fieldError ?? submitError

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="app-header-row">
          <div>
            <h1>{config.app_name}</h1>
            <p>Version {config.version}</p>
          </div>
          <a href="https://github.com/pypi-ahmad/DocuMind/blob/main/docs/user-guide.md" target="_blank" rel="noopener noreferrer" className="header-link">Help & Docs</a>
        </div>
      </header>

      <WorkflowPresetCards
        presets={PRESET_OPTIONS}
        selectedPreset={selectedPreset}
        disabled={isActionBusy}
        onSelect={setSelectedPreset}
        onClear={() => setSelectedPreset(null)}
      />

      {selectedPreset === null ? (
        <section className="layout-grid section-gap">
          <section className="card">
            <h2>Providers</h2>
            <ul className="provider-list">
              {config.providers.map((provider) => (
                <li key={provider.provider} className="provider-item">
                  <strong>{provider.provider}</strong>
                  <div className="provider-flags">
                    {provider.requires_api_key ? <span className="provider-badge badge-key">Requires API key</span> : <span className="provider-badge badge-ok">No key needed</span>}
                    {provider.has_env_key ? <span className="provider-badge badge-ok">Server key configured</span> : provider.requires_api_key ? <span className="provider-badge badge-warn">No server key</span> : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h2>OCR Engines</h2>
            <ul className="inline-list">
              {config.ocr.supported_ocr_engines.map((engine) => (
                <li key={engine}>{engine}</li>
              ))}
            </ul>
            <h2>Retrieval Modes</h2>
            <ul className="inline-list">
              {config.retrieval.supported_retrieval_modes.map((mode) => (
                <li key={mode}>{mode}</li>
              ))}
            </ul>
          </section>
        </section>
      ) : null}

      {selectedPreset === null ? (
        <section className="card section-gap">
          <h2>Advanced API Form</h2>
          <div className="control-row">
            <label className="field-group" htmlFor="action-select">
              <span className="field-label">Select action</span>
              <select
                id="action-select"
                value={selectedAction}
                disabled={isActionBusy}
                onChange={(event) => setSelectedAction(event.target.value as ActionKey)}
              >
                {Object.keys(forms).map((key) => (
                  <option key={key} value={key}>
                    {ACTION_LABELS[key as ActionKey]}
                  </option>
                ))}
              </select>
            </label>
            {supportsJobMode ? (
              <p className="field-help">This action supports background job mode.</p>
            ) : null}
          </div>
        </section>
      ) : (
        <section className="card section-gap preset-active-card">
          <h2>{activePreset?.title}</h2>
          <p className="field-help">{activePreset?.description}</p>
        </section>
      )}

      <section className="layout-grid section-gap">
        <div>
          {selectorConfig ? (
            <section className="card form-section-stack-item">
              <h2>{usesEmbeddingSelector ? 'Embedding Provider & Model' : 'Provider & Model'}</h2>
              <ProviderModelSelector
                providers={config.providers}
                selectedProvider={selectedProvider}
                selectedModel={selectedModel}
                apiKey={apiKey}
                providerLabel={selectorConfig.providerLabel}
                modelLabel={selectorConfig.modelLabel}
                disabled={isActionBusy}
                onProviderChange={setSelectedProvider}
                onModelChange={setSelectedModel}
                onApiKeyChange={setApiKey}
              />
              {CLOUD_PROVIDERS.has(selectedProvider) ? (
                <p className="field-help byok-note">
                  Entering a key here overrides the server default for this browser session only. Leaving it blank uses the
                  server&apos;s configured key if available.
                </p>
              ) : null}
            </section>
          ) : null}

          {usesPipelineSelector ? (
            <div className="form-section-stack-item">
              <PipelineSelector
                pipelines={pipelines}
                isLoading={isLoadingPipelines}
                error={pipelineError}
                selectedPipeline={selectedPipelineName}
                disabled={isActionBusy}
                onChange={setSelectedPipelineName}
              />
            </div>
          ) : null}

          {selectedPreset !== null && visibleFields.some((f) => f.name === 'file_path') ? (
            <div className="form-section-stack-item">
              <section className="card">
                <FileUpload
                  disabled={isActionBusy}
                  onFilePathResolved={(filePath) => handleFieldChange('file_path', filePath)}
                />
              </section>
            </div>
          ) : null}

          <DynamicForm
            actionLabel={activePreset?.title ?? ACTION_LABELS[currentAction]}
            descriptor={currentDescriptor}
            values={formValues}
            excludeFields={
              selectedPreset === null
                ? usesLlmSelector ? GENERIC_SELECTOR_FIELDS : undefined
                : visibleFields.some((f) => f.name === 'file_path')
                  ? new Set(['file_path'])
                  : undefined
            }
            fieldError={fieldError}
            submitError={submitError}
            isSubmitting={isSubmitting}
            disabled={isActionBusy}
            submitMode={submitMode}
            supportsJobMode={supportsJobMode}
            isPresetMode={selectedPreset !== null}
            onSubmitModeChange={setSubmitMode}
            onChange={handleFieldChange}
            onSubmit={handleSubmit}
          />

          {selectedPreset === 'ask_indexed_documents' ? (
            <div className="form-section-stack-item">
              <IndexedDocumentsList
                documents={indexedDocuments}
                isLoading={isLoadingIndexedDocuments}
                error={indexedDocumentsError}
              />
            </div>
          ) : null}
        </div>

        <div className="result-column">
          {workflowSteps.length > 0 ? <WorkflowStatus title="Workflow Status" steps={workflowSteps} /> : null}

          {requestPreview !== null ? <JsonBlock title="Request Preview" value={requestPreview} /> : null}

          {intermediateResult !== null ? <FormattedResult title="Intermediate OCR Result" value={intermediateResult} /> : null}

          {submittedJob ? (
            <>
              <JsonBlock title="Job Submission" value={submittedJob} />
              <section className="card result-section">
                <h2>Job Status</h2>
                <JobPoller job={submittedJob} onJobUpdate={handleJobUpdate} />
              </section>
            </>
          ) : null}

          {responseData !== null && !activeError ? (
            <p className="message success">Done — your results are ready.</p>
          ) : null}

          {responseData !== null ? <FormattedResult title="Response" value={responseData} /> : null}

          {activeError ? <JsonBlock title="Error" value={{ error: activeError }} /> : null}

          {requestPreview === null && intermediateResult === null && submittedJob === null && responseData === null && !activeError ? (
            <section className="card welcome-card">
              <h2>Welcome to DocuMind</h2>
              <p className="field-help">Choose a workflow above to process your first document, or switch to advanced mode for full API access.</p>
            </section>
          ) : null}
        </div>
      </section>
    </main>
  )
}
