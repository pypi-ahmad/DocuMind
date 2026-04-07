import { useState } from 'react'

import { JsonBlock } from './JsonBlock'

interface FormattedResultProps {
  title: string
  value: unknown
}

function isTextResponse(value: unknown): value is { text: string } {
  return Boolean(value && typeof value === 'object' && 'text' in value && typeof (value as Record<string, unknown>).text === 'string')
}

function isAnswerResponse(value: unknown): value is { answer: string; sources?: unknown[] } {
  return Boolean(value && typeof value === 'object' && 'answer' in value && typeof (value as Record<string, unknown>).answer === 'string')
}

function isKeyFieldsResponse(value: unknown): value is { key_fields: Record<string, unknown> } {
  return Boolean(
    value &&
      typeof value === 'object' &&
      'key_fields' in value &&
      typeof (value as Record<string, unknown>).key_fields === 'object' &&
      (value as Record<string, unknown>).key_fields !== null,
  )
}

function isOCRExtractResponse(value: unknown): value is { text: string; pages?: unknown[] } {
  return Boolean(
    value &&
      typeof value === 'object' &&
      'text' in value &&
      typeof (value as Record<string, unknown>).text === 'string' &&
      ('normalization' in value || 'pages' in value),
  )
}

function downloadJson(value: unknown) {
  const jsonText = JSON.stringify(value, null, 2)
  const blob = new Blob([jsonText], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const a = document.createElement('a')
  a.href = url
  a.download = `documind-result-${timestamp}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function copyText(text: string, setCopied: (v: boolean) => void) {
  void navigator.clipboard.writeText(text).then(() => {
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  })
}

export function FormattedResult({ title, value }: FormattedResultProps) {
  const [copied, setCopied] = useState(false)

  // OCR extraction with text + normalization/pages
  if (isOCRExtractResponse(value)) {
    return (
      <section className="card">
        <div className="json-block-header">
          <h2>{title}</h2>
          <div className="json-block-actions">
            <button type="button" className="small-action-button" onClick={() => copyText(value.text, setCopied)}>
              {copied ? 'Copied!' : 'Copy text'}
            </button>
            <button type="button" className="small-action-button" onClick={() => downloadJson(value)}>
              Download JSON
            </button>
          </div>
        </div>
        <div className="formatted-prose">{value.text}</div>
        <JsonBlock title="Show raw JSON" value={value} collapsible />
      </section>
    )
  }

  // QA answer with optional sources
  if (isAnswerResponse(value)) {
    return (
      <section className="card">
        <div className="json-block-header">
          <h2>{title}</h2>
          <div className="json-block-actions">
            <button type="button" className="small-action-button" onClick={() => copyText(value.answer, setCopied)}>
              {copied ? 'Copied!' : 'Copy answer'}
            </button>
            <button type="button" className="small-action-button" onClick={() => downloadJson(value)}>
              Download JSON
            </button>
          </div>
        </div>
        <div className="formatted-prose">{value.answer}</div>
        {value.sources && Array.isArray(value.sources) && value.sources.length > 0 && (
          <div className="sources-section">
            <h3>Sources</h3>
            <ul className="source-list">
              {value.sources.map((source, i) => (
                <li key={i} className="source-item">
                  <pre className="metadata-preview">{JSON.stringify(source, null, 2)}</pre>
                </li>
              ))}
            </ul>
          </div>
        )}
        <JsonBlock title="Show raw JSON" value={value} collapsible />
      </section>
    )
  }

  // Key fields extraction
  if (isKeyFieldsResponse(value)) {
    const fields = value.key_fields
    return (
      <section className="card">
        <div className="json-block-header">
          <h2>{title}</h2>
          <div className="json-block-actions">
            <button type="button" className="small-action-button" onClick={() => copyText(JSON.stringify(fields, null, 2), setCopied)}>
              {copied ? 'Copied!' : 'Copy fields'}
            </button>
            <button type="button" className="small-action-button" onClick={() => downloadJson(value)}>
              Download JSON
            </button>
          </div>
        </div>
        <table className="key-fields-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(fields).map(([key, val]) => (
              <tr key={key}>
                <td className="key-field-name">{key}</td>
                <td>{typeof val === 'object' ? JSON.stringify(val) : String(val ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <JsonBlock title="Show raw JSON" value={value} collapsible />
      </section>
    )
  }

  // LLM text response (summary, generation, etc.)
  if (isTextResponse(value)) {
    return (
      <section className="card">
        <div className="json-block-header">
          <h2>{title}</h2>
          <div className="json-block-actions">
            <button type="button" className="small-action-button" onClick={() => copyText(value.text, setCopied)}>
              {copied ? 'Copied!' : 'Copy text'}
            </button>
            <button type="button" className="small-action-button" onClick={() => downloadJson(value)}>
              Download JSON
            </button>
          </div>
        </div>
        <div className="formatted-prose">{value.text}</div>
        <JsonBlock title="Show raw JSON" value={value} collapsible />
      </section>
    )
  }

  // Fallback: raw JSON with download
  return (
    <section className="card">
      <div className="json-block-header">
        <h2>{title}</h2>
        <div className="json-block-actions">
          <button type="button" className="small-action-button" onClick={() => copyText(JSON.stringify(value, null, 2), setCopied)}>
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button type="button" className="small-action-button" onClick={() => downloadJson(value)}>
            Download JSON
          </button>
        </div>
      </div>
      <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>
    </section>
  )
}
