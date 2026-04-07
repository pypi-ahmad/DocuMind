import type { FormEvent } from 'react'

import type { FormState, SubmitMode, UIFormDescriptor, UIFormField } from '../types'

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
  isPresetMode?: boolean
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
        placeholder={field.placeholder || `{\n  "key": "value"\n}`}
        rows={6}
        disabled={disabled}
        onChange={(event) => onChange(field.name, event.target.value)}
      />
    )
  }

  if (field.type === 'boolean') {
    const checked = value === 'true' || value === true
    return (
      <label className="toggle-row" htmlFor={`${field.name}-toggle`}>
        <input
          id={`${field.name}-toggle`}
          type="checkbox"
          className="toggle-checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(field.name, event.target.checked ? 'true' : 'false')}
        />
        <span className="toggle-label">{checked ? 'On' : 'Off'}</span>
      </label>
    )
  }

  if (field.type === 'integer' || field.type === 'number') {
    return (
      <input
        id={field.name}
        type="number"
        step={field.type === 'integer' ? '1' : 'any'}
        value={typeof value === 'string' ? value : ''}
        placeholder={field.placeholder ?? ''}
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
      placeholder={field.placeholder ?? ''}
      disabled={disabled}
      onChange={(event) => onChange(field.name, event.target.value)}
    />
  )
}

function FieldRow({
  field,
  value,
  disabled,
  onChange,
}: {
  field: UIFormField
  value: string | boolean | undefined
  disabled: boolean
  onChange: (fieldName: string, value: string | boolean) => void
}) {
  return (
    <label key={field.name} className="field-group" htmlFor={field.name}>
      <span className="field-label">
        {field.label || field.name}
        {field.required ? <strong className="required-marker"> *</strong> : null}
      </span>
      <span className="field-help">{field.description}</span>
      {renderInput(field, value, disabled, onChange)}
    </label>
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
  isPresetMode = false,
  onSubmitModeChange,
  onChange,
  onSubmit,
}: DynamicFormProps) {
  const visibleFields = excludeFields
    ? descriptor.fields.filter((f) => !excludeFields.has(f.name))
    : descriptor.fields

  const requiredFields = visibleFields.filter((f) => f.required)
  const optionalFields = visibleFields.filter((f) => !f.required)

  return (
    <section className="card">
      <h2>{actionLabel}</h2>
      <form className="form-grid" onSubmit={onSubmit}>
        {requiredFields.map((field) => (
          <FieldRow key={field.name} field={field} value={values[field.name]} disabled={disabled} onChange={onChange} />
        ))}

        {optionalFields.length > 0 && (
          <details className="advanced-options">
            <summary className="advanced-options-toggle">Advanced options ({optionalFields.length})</summary>
            <div className="form-grid advanced-options-content">
              {optionalFields.map((field) => (
                <FieldRow key={field.name} field={field} value={values[field.name]} disabled={disabled} onChange={onChange} />
              ))}
            </div>
          </details>
        )}

        {supportsJobMode && !isPresetMode && (
          <label className="field-group" htmlFor="submit-mode">
            <span className="field-label">How to run</span>
            <select
              id="submit-mode"
              value={submitMode}
              disabled={disabled}
              onChange={(e) => onSubmitModeChange(e.target.value as SubmitMode)}
            >
              <option value="direct">Run immediately</option>
              <option value="job">Run in background</option>
            </select>
          </label>
        )}

        {fieldError ? <p className="message error">{fieldError}</p> : null}
        {submitError ? <p className="message error">{submitError}</p> : null}

        <button type="submit" disabled={disabled || isSubmitting}>
          {isSubmitting ? 'Submitting…' : isPresetMode ? actionLabel : submitMode === 'job' && supportsJobMode ? 'Submit Job' : 'Submit'}
        </button>
      </form>
    </section>
  )
}
