import type { WorkflowStepStatus } from '../types'

const STEP_STATUS_LABELS: Record<string, string> = {
  pending: 'Waiting',
  running: 'In progress…',
  completed: 'Done',
  failed: 'Failed',
}

interface WorkflowStatusProps {
  title: string
  steps: WorkflowStepStatus[]
}

export function WorkflowStatus({ title, steps }: WorkflowStatusProps) {
  if (steps.length === 0) {
    return null
  }

  return (
    <section className="card">
      <h2>{title}</h2>
      <ol className="workflow-steps">
        {steps.map((step) => (
          <li key={step.label} className="workflow-step-item">
            <div className="workflow-step-header">
              <strong>{step.label}</strong>
              <span className={`status-badge ${step.status === 'completed' ? 'success' : step.status === 'failed' ? 'error' : 'info'}`}>
                {STEP_STATUS_LABELS[step.status] ?? step.status}
              </span>
            </div>
            {step.detail ? <p className="field-help">{step.detail}</p> : null}
          </li>
        ))}
      </ol>
    </section>
  )
}
