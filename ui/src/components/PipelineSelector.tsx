import type { PipelineSummary } from '../types'

const PIPELINE_LABELS: Record<string, string> = {
  ocr_extract_only: 'Extract Text Only',
  ocr_extract_then_summary: 'Extract & Summarize',
  ocr_extract_then_key_fields: 'Extract & Get Key Fields',
}

function humanizePipelineName(name: string): string {
  return (
    PIPELINE_LABELS[name] ??
    name
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  )
}

interface PipelineSelectorProps {
  pipelines: PipelineSummary[]
  isLoading: boolean
  error: string | null
  selectedPipeline: string
  disabled?: boolean
  onChange: (pipelineName: string) => void
}

export function PipelineSelector({
  pipelines,
  isLoading,
  error,
  selectedPipeline,
  disabled = false,
  onChange,
}: PipelineSelectorProps) {
  return (
    <section className="card">
      <h2>Pipeline</h2>
      {isLoading ? (
        <p className="message info">Loading pipelines…</p>
      ) : pipelines.length > 0 ? (
        <label className="field-group" htmlFor="pipeline-name-select">
          <span className="field-label">Pipeline Name <strong className="required-marker">*</strong></span>
          <select
            id="pipeline-name-select"
            value={selectedPipeline}
            onChange={(event) => onChange(event.target.value)}
            disabled={disabled}
          >
            {pipelines.map((pipeline) => (
              <option key={pipeline.pipeline_name} value={pipeline.pipeline_name}>
                {humanizePipelineName(pipeline.pipeline_name)}
              </option>
            ))}
          </select>
          <span className="field-help">
            {pipelines.find((pipeline) => pipeline.pipeline_name === selectedPipeline)?.description ?? 'Select a named pipeline.'}
          </span>
        </label>
      ) : (
        <label className="field-group" htmlFor="pipeline-name-input">
          <span className="field-label">Pipeline Name <strong className="required-marker">*</strong></span>
          <input
            id="pipeline-name-input"
            type="text"
            value={selectedPipeline}
            placeholder="e.g. ocr_extract_then_summary"
            onChange={(event) => onChange(event.target.value)}
            disabled={disabled}
          />
          <span className="field-help">
            {error ? `Pipeline list unavailable: ${error}. Enter a pipeline name manually.` : 'Enter a pipeline name manually.'}
          </span>
        </label>
      )}
    </section>
  )
}
