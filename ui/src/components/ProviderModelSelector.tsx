import { useEffect, useState } from 'react'

import { fetchProviderModels } from '../api'
import type { ModelOption, UIProviderOption } from '../types'

interface ProviderModelSelectorProps {
  providers: UIProviderOption[]
  selectedProvider: string
  selectedModel: string
  apiKey: string
  providerLabel?: string
  modelLabel?: string
  disabled?: boolean
  onProviderChange: (provider: string) => void
  onModelChange: (model: string) => void
  onApiKeyChange: (key: string) => void
}

const BYOK_PROVIDERS = new Set(['openai', 'gemini', 'anthropic'])

export function ProviderModelSelector({
  providers,
  selectedProvider,
  selectedModel,
  apiKey,
  providerLabel = 'Provider',
  modelLabel = 'Model',
  disabled = false,
  onProviderChange,
  onModelChange,
  onApiKeyChange,
}: ProviderModelSelectorProps) {
  const [models, setModels] = useState<ModelOption[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [modelError, setModelError] = useState<string | null>(null)
  const [manualInput, setManualInput] = useState(false)

  const providerMeta = providers.find((p) => p.provider === selectedProvider)
  const showApiKeyInput = BYOK_PROVIDERS.has(selectedProvider)

  useEffect(() => {
    setModels([])
    setModelError(null)
    setManualInput(false)
    onModelChange('')
  }, [selectedProvider])

  useEffect(() => {
    if (!selectedProvider) {
      return
    }

    let cancelled = false

    async function load() {
      setIsLoadingModels(true)
      setModelError(null)
      setModels([])
      setManualInput(false)

      try {
        const resolvedApiKey = BYOK_PROVIDERS.has(selectedProvider) && apiKey.trim() ? apiKey.trim() : undefined
        const response = await fetchProviderModels(selectedProvider, resolvedApiKey)
        if (cancelled) return
        setModels(response.models)
        if (response.models.length > 0) {
          onModelChange(response.models[0].id)
        }
      } catch (error) {
        if (cancelled) return
        setModelError(error instanceof Error ? error.message : 'Failed to load models')
        setManualInput(true)
      } finally {
        if (!cancelled) setIsLoadingModels(false)
      }
    }

    void load()
    return () => { cancelled = true }
  }, [selectedProvider, apiKey])

  return (
    <div className="provider-model-selector">
      <label className="field-group" htmlFor="pms-provider">
        <span className="field-label">{providerLabel} <strong className="required-marker">*</strong></span>
        <select
          id="pms-provider"
          value={selectedProvider}
          disabled={disabled}
          onChange={(e) => onProviderChange(e.target.value)}
        >
          {providers.map((p) => (
            <option key={p.provider} value={p.provider}>{p.provider}</option>
          ))}
        </select>
      </label>

      {showApiKeyInput && (
        <label className="field-group" htmlFor="pms-apikey">
          <span className="field-label">API Key</span>
          <span className="field-help">
            {providerMeta?.has_env_key
              ? 'Server has a configured key. Enter one here to override it for this session.'
              : 'No server key configured. Provide your own key (BYOK) for this session.'}
          </span>
          <input
            id="pms-apikey"
            type="password"
            autoComplete="off"
            value={apiKey}
            placeholder="sk-… (session only, never stored)"
            disabled={disabled}
            onChange={(e) => onApiKeyChange(e.target.value)}
          />
        </label>
      )}

      <label className="field-group" htmlFor="pms-model">
        <span className="field-label">{modelLabel} <strong className="required-marker">*</strong></span>
        {isLoadingModels ? (
          <p className="message info">Loading models…</p>
        ) : modelError && !manualInput ? (
          <p className="message error">{modelError}</p>
        ) : manualInput ? (
          <>
            <span className="field-help">Could not load models: {modelError}. Type a model name manually.</span>
            <input
              id="pms-model"
              type="text"
              value={selectedModel}
              placeholder="e.g. llama3, gpt-4o"
              disabled={disabled}
              onChange={(e) => onModelChange(e.target.value)}
            />
          </>
        ) : (
          <select
            id="pms-model"
            value={selectedModel}
            disabled={disabled}
            onChange={(e) => onModelChange(e.target.value)}
          >
            {models.length === 0 && <option value="">No models available</option>}
            {models.map((m) => (
              <option key={m.id} value={m.id}>{m.display_name}</option>
            ))}
          </select>
        )}
      </label>
    </div>
  )
}
