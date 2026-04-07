import { useState } from 'react'

interface JsonBlockProps {
  title: string
  value: unknown
  collapsible?: boolean
}

export function JsonBlock({ title, value, collapsible = false }: JsonBlockProps) {
  const [copied, setCopied] = useState(false)
  const jsonText = JSON.stringify(value, null, 2)

  function handleCopy() {
    void navigator.clipboard.writeText(jsonText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const content = (
    <>
      <div className="json-block-header">
        {!collapsible && <h2>{title}</h2>}
        <div className="json-block-actions">
          <button type="button" className="small-action-button" onClick={handleCopy}>
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>
      <pre className="json-block">{jsonText}</pre>
    </>
  )

  if (collapsible) {
    return (
      <details className="card json-block-collapsible">
        <summary className="advanced-options-toggle">{title}</summary>
        {content}
      </details>
    )
  }

  return (
    <section className="card">
      {content}
    </section>
  )
}
