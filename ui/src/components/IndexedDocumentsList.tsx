import { useState } from 'react'

import type { DocumentSummary } from '../types'

interface IndexedDocumentsListProps {
  documents: DocumentSummary[]
  isLoading: boolean
  error: string | null
  onClearAll?: () => Promise<void>
  onDeleteOne?: (docId: string) => Promise<void>
}

function DocumentItem({
  document,
  onDelete,
}: {
  document: DocumentSummary
  onDelete?: (docId: string) => Promise<void>
}) {
  const [confirming, setConfirming] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [showMeta, setShowMeta] = useState(false)

  const hasMeta = document.metadata && Object.keys(document.metadata).length > 0

  async function handleDelete() {
    if (!onDelete) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await onDelete(document.doc_id)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Could not remove document.')
      setIsDeleting(false)
      setConfirming(false)
    }
  }

  return (
    <li className="document-summary-item">
      <div className="doc-item-header">
        <strong className="doc-item-id">{document.doc_id}</strong>
        <div className="doc-item-actions">
          <span className="doc-section-count">{document.chunk_count} section{document.chunk_count !== 1 ? 's' : ''}</span>
          {hasMeta && (
            <button type="button" className="text-link" onClick={() => setShowMeta((v) => !v)}>
              {showMeta ? 'Hide details' : 'Details'}
            </button>
          )}
          {onDelete && !confirming && (
            <button type="button" className="text-link danger-link" onClick={() => { setDeleteError(null); setConfirming(true) }}>
              Remove
            </button>
          )}
        </div>
      </div>

      {confirming && (
        <div className="clear-confirm">
          <p className="message error">Remove &ldquo;{document.doc_id}&rdquo;? This cannot be undone.</p>
          <div className="clear-confirm-actions">
            <button type="button" className="small-action-button danger-button" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? 'Removing…' : 'Yes, remove'}
            </button>
            <button type="button" className="small-action-button" onClick={() => setConfirming(false)} disabled={isDeleting}>
              Cancel
            </button>
          </div>
          {deleteError ? <p className="message error">{deleteError}</p> : null}
        </div>
      )}

      {showMeta && hasMeta && (
        <pre className="metadata-preview">{JSON.stringify(document.metadata, null, 2)}</pre>
      )}
    </li>
  )
}

export function IndexedDocumentsList({ documents, isLoading, error, onClearAll, onDeleteOne }: IndexedDocumentsListProps) {
  const [confirming, setConfirming] = useState(false)
  const [isClearing, setIsClearing] = useState(false)
  const [clearError, setClearError] = useState<string | null>(null)

  async function handleConfirmClear() {
    if (!onClearAll) return
    setIsClearing(true)
    setClearError(null)
    try {
      await onClearAll()
      setConfirming(false)
    } catch (err) {
      setClearError(err instanceof Error ? err.message : 'Could not clear documents.')
    } finally {
      setIsClearing(false)
    }
  }

  return (
    <section className="card">
      <div className="indexed-docs-header">
        <h2>
          Indexed Documents
          {documents.length > 0 ? <span className="doc-count-badge">{documents.length}</span> : null}
        </h2>
        {onClearAll && documents.length > 0 && !confirming ? (
          <button type="button" className="text-link danger-link" onClick={() => { setClearError(null); setConfirming(true) }}>
            Clear all
          </button>
        ) : null}
      </div>

      {confirming ? (
        <div className="clear-confirm">
          <p className="message error">Remove all {documents.length} indexed document{documents.length !== 1 ? 's' : ''}? This cannot be undone.</p>
          <div className="clear-confirm-actions">
            <button type="button" className="small-action-button danger-button" onClick={handleConfirmClear} disabled={isClearing}>
              {isClearing ? 'Clearing…' : 'Yes, clear all'}
            </button>
            <button type="button" className="small-action-button" onClick={() => setConfirming(false)} disabled={isClearing}>
              Cancel
            </button>
          </div>
          {clearError ? <p className="message error">{clearError}</p> : null}
        </div>
      ) : null}

      {isLoading ? <p className="message info">Loading indexed document summaries…</p> : null}
      {error ? <p className="message error">{error}</p> : null}
      {!isLoading && !error && documents.length === 0 ? (
        <p className="field-help">
          No documents indexed yet. Use the <strong>Index Document</strong> workflow to add documents, then come back here to search them.
        </p>
      ) : null}

      {!isLoading && !error && documents.length > 0 ? (
        <ul className="document-summary-list">
          {documents.map((document) => (
            <DocumentItem key={document.doc_id} document={document} onDelete={onDeleteOne} />
          ))}
        </ul>
      ) : null}
    </section>
  )
}
