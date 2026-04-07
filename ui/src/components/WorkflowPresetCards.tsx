import type { WorkflowPresetKey } from '../types'

interface WorkflowPresetCardItem {
  key: WorkflowPresetKey
  title: string
  description: string
  flowLabel: string
}

interface WorkflowPresetCardsProps {
  presets: WorkflowPresetCardItem[]
  selectedPreset: WorkflowPresetKey | null
  disabled?: boolean
  onSelect: (preset: WorkflowPresetKey) => void
  onClear: () => void
}

export function WorkflowPresetCards({
  presets,
  selectedPreset,
  disabled = false,
  onSelect,
  onClear,
}: WorkflowPresetCardsProps) {
  return (
    <section className="card preset-section">
      <div className="preset-section-header">
        <div>
          <h2>What would you like to do?</h2>
          <p className="field-help">Choose a task to get started.</p>
        </div>
        <button type="button" className="secondary-button" onClick={onClear} disabled={disabled || selectedPreset === null}>
          Advanced mode
        </button>
      </div>

      <div className="preset-grid">
        {presets.map((preset) => {
          const isActive = selectedPreset === preset.key
          return (
            <button
              key={preset.key}
              type="button"
              className={`preset-card${isActive ? ' active' : ''}`}
              onClick={() => onSelect(preset.key)}
              disabled={disabled}
            >
              <span className="preset-flow-label">{preset.flowLabel}</span>
              <strong>{preset.title}</strong>
              <span>{preset.description}</span>
            </button>
          )
        })}
      </div>
    </section>
  )
}
