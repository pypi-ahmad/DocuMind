import type { DocumentSummary } from '../types'

interface IndexedDocumentsListProps {
  documents: DocumentSummary[]
  isLoading: boolean
  error: string | null
}

export function IndexedDocumentsList({ documents, isLoading, error }: IndexedDocumentsListProps) {
  return (
    <section className="card">
      <h2>Indexed Documents</h2>
      {isLoading ? <p className="message info">Loading indexed document summaries…</p> : null}
      {error ? <p className="message error">{error}</p> : null}
      {!isLoading && !error && documents.length === 0 ? <p className="field-help">No indexed documents found.</p> : null}

      {!isLoading && !error && documents.length > 0 ? (
        <ul className="document-summary-list">
          {documents.map((document) => (
            <li key={document.doc_id} className="document-summary-item">
              <strong>{document.doc_id}</strong>
              <span className="field-help">Chunks: {document.chunk_count}</span>
              <pre className="metadata-preview">{JSON.stringify(document.metadata, null, 2)}</pre>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
