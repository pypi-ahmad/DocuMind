import { type DragEvent, useRef, useState } from 'react'

import { uploadDocument } from '../api'

interface FileUploadProps {
  onFilePathResolved: (filePath: string) => void
  disabled?: boolean
}

const ACCEPT = '.png,.jpg,.jpeg,.webp,.pdf'

export function FileUpload({ onFilePathResolved, disabled = false }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadedName, setUploadedName] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    setUploadError(null)
    setUploadedName(null)
    setIsUploading(true)

    try {
      const result = await uploadDocument(file)
      setUploadedName(file.name)
      onFilePathResolved(result.file_path)
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault()
    if (!disabled && !isUploading) {
      setIsDragging(true)
    }
  }

  function handleDragLeave(event: DragEvent) {
    event.preventDefault()
    setIsDragging(false)
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault()
    setIsDragging(false)
    if (disabled || isUploading) return

    const file = event.dataTransfer.files[0]
    if (file) {
      void handleFile(file)
    }
  }

  function handleClick() {
    if (!disabled && !isUploading) {
      inputRef.current?.click()
    }
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) {
      void handleFile(file)
    }
    // Reset so same file can be re-selected
    event.target.value = ''
  }

  return (
    <label className="field-group">
      <span className="field-label">Document file <strong className="required-marker">*</strong></span>
      <span className="field-help">Upload an image or PDF from your computer.</span>
      <div
        className={`file-drop-zone${isDragging ? ' dragging' : ''}${isUploading ? ' uploading' : ''}${uploadedName ? ' uploaded' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick() }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="file-input-hidden"
          onChange={handleInputChange}
          disabled={disabled || isUploading}
        />
        {isUploading ? (
          <span className="file-drop-text">Uploading…</span>
        ) : uploadedName ? (
          <span className="file-drop-text">✓ {uploadedName} — click or drop to replace</span>
        ) : (
          <span className="file-drop-text">Drag & drop a file here, or click to browse</span>
        )}
      </div>
      {uploadError ? <p className="message error">{uploadError}</p> : null}
    </label>
  )
}
