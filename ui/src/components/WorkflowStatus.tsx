import type { WorkflowStepStatus } from '../types'

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
                {step.status}
              </span>
            </div>
            {step.detail ? <p className="field-help">{step.detail}</p> : null}
          </li>
        ))}
      </ol>
    </section>
  )
}
