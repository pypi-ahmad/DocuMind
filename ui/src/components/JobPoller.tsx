import { useEffect, useRef, useState } from 'react'

import { fetchJob } from '../api'
import type { JobResponse } from '../types'
import { FormattedResult } from './FormattedResult'
import { JsonBlock } from './JsonBlock'

interface JobPollerProps {
  job: JobResponse
  onJobUpdate?: (job: JobResponse) => void
  isPresetMode?: boolean
}

const POLL_INTERVAL_MS = 2000
const JOB_STATUS_LABELS: Record<string, string> = {
  pending: 'Waiting…',
  processing: 'In progress…',
  completed: 'Done',
  failed: 'Failed',
}

const TERMINAL_STATUSES = new Set(['completed', 'failed'])

export function JobPoller({ job: initialJob, onJobUpdate, isPresetMode = false }: JobPollerProps) {
  const [job, setJob] = useState<JobResponse>(initialJob)
  const [pollError, setPollError] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    setJob(initialJob)
    setPollError(null)
    onJobUpdate?.(initialJob)

    if (TERMINAL_STATUSES.has(initialJob.status)) {
      return
    }

    const timer = setInterval(async () => {
      try {
        const updated = await fetchJob(initialJob.job_id)
        setJob(updated)
        onJobUpdate?.(updated)
        if (TERMINAL_STATUSES.has(updated.status)) {
          clearInterval(timer)
        }
      } catch (error) {
        setPollError(error instanceof Error ? error.message : 'Polling failed')
        clearInterval(timer)
      }
    }, POLL_INTERVAL_MS)

    timerRef.current = timer

    return () => clearInterval(timer)
  }, [initialJob, onJobUpdate])

  const isTerminal = TERMINAL_STATUSES.has(job.status)
  const statusClass = job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'info'

  return (
    <div className="job-poller">
      {!isPresetMode && (
        <div className="job-status-row">
          <span className="field-label">Job ID:</span> <code>{job.job_id}</code>
        </div>
      )}
      <div className="job-status-row">
        <span className="field-label">Status:</span>{' '}
        <span className={`status-badge ${statusClass}`}>
          {isPresetMode ? (JOB_STATUS_LABELS[job.status] ?? job.status) : job.status}
        </span>
        {!isTerminal && !pollError && <span className="spinner" />}
      </div>

      {pollError && (
        isPresetMode
          ? <p className="message error">{pollError}</p>
          : <JsonBlock title="Polling Error" value={{ error: pollError }} />
      )}

      {job.status === 'failed' && job.error && (
        isPresetMode
          ? <p className="message error">{job.error}</p>
          : <JsonBlock title="Job Error" value={{ error: job.error }} />
      )}

      {job.status === 'completed' && job.result && (
        <FormattedResult title="Job Result" value={job.result} />
      )}

      {isPresetMode && (
        <details className="technical-details">
          <summary className="technical-details-toggle">Technical details</summary>
          <div className="technical-details-content">
            <div className="job-status-row">
              <span className="field-label">Job ID:</span> <code>{job.job_id}</code>
            </div>
            <div className="job-status-row">
              <span className="field-label">Raw status:</span> <code>{job.status}</code>
            </div>
          </div>
        </details>
      )}
    </div>
  )
}
