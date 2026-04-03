import type { FormEvent } from 'react'

import type { ActionKey, FormState, SubmitMode, UIFormDescriptor, UIFormField } from '../types'

interface DynamicFormProps {
  actionLabel: string
  descriptor: UIFormDescriptor
  values: FormState
  excludeFields?: Set<string>
  fieldError: string | null
  submitError: string | null
  isSubmitting: boolean
  disabled?: boolean
  submitMode: SubmitMode
  supportsJobMode: boolean
  onSubmitModeChange: (mode: SubmitMode) => void
  onChange: (fieldName: string, value: string | boolean) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

function renderInput(
  field: UIFormField,
  value: string | boolean | undefined,
  disabled: boolean,
  onChange: (fieldName: string, value: string | boolean) => void,
) {
  if (field.type === 'object') {
    return (
      <textarea
        id={field.name}
        value={typeof value === 'string' ? value : ''}
        placeholder={`{\n  "key": "value"\n}`}
        rows={6}
        disabled={disabled}
        onChange={(event) => onChange(field.name, event.target.value)}
      />
    )
  }

  if (field.type === 'boolean') {
    return (
      <select
        id={field.name}
        value={typeof value === 'string' ? value : ''}
          disabled={disabled}
        onChange={(event) => onChange(field.name, event.target.value)}
      >
        <option value="">Use backend default</option>
        <option value="true">True</option>
        <option value="false">False</option>
      </select>
    )
  }

  if (field.type === 'integer' || field.type === 'number') {
    return (
      <input
        id={field.name}
        type="number"
        step={field.type === 'integer' ? '1' : 'any'}
        value={typeof value === 'string' ? value : ''}
        disabled={disabled}
        onChange={(event) => onChange(field.name, event.target.value)}
      />
    )
  }

  return (
    <input
      id={field.name}
      type="text"
      value={typeof value === 'string' ? value : ''}
      disabled={disabled}
      onChange={(event) => onChange(field.name, event.target.value)}
    />
  )
}

export function DynamicForm({
  actionLabel,
  descriptor,
  values,
  excludeFields,
  fieldError,
  submitError,
  isSubmitting,
  disabled = false,
  submitMode,
  supportsJobMode,
  onSubmitModeChange,
  onChange,
  onSubmit,
}: DynamicFormProps) {
  const visibleFields = excludeFields
    ? descriptor.fields.filter((f) => !excludeFields.has(f.name))
    : descriptor.fields

  return (
    <section className="card">
      <h2>{actionLabel}</h2>
      <form className="form-grid" onSubmit={onSubmit}>
        {visibleFields.map((field) => (
          <label key={field.name} className="field-group" htmlFor={field.name}>
            <span className="field-label">
              {field.name}
              {field.required ? <strong className="required-marker"> *</strong> : null}
            </span>
            <span className="field-help">{field.description}</span>
            {renderInput(field, values[field.name], disabled, onChange)}
          </label>
        ))}

        {supportsJobMode && (
          <label className="field-group" htmlFor="submit-mode">
            <span className="field-label">Submit mode</span>
            <select
              id="submit-mode"
              value={submitMode}
              disabled={disabled}
              onChange={(e) => onSubmitModeChange(e.target.value as SubmitMode)}
            >
              <option value="direct">Direct request</option>
              <option value="job">Submit as background job</option>
            </select>
          </label>
        )}

        {fieldError ? <p className="message error">{fieldError}</p> : null}
        {submitError ? <p className="message error">{submitError}</p> : null}

        <button type="submit" disabled={disabled || isSubmitting}>
          {isSubmitting ? 'Submitting…' : submitMode === 'job' && supportsJobMode ? 'Submit Job' : 'Submit'}
        </button>
      </form>
    </section>
  )
}
