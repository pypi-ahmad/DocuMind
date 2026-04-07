import { useEffect, useRef, useState } from 'react'

import { fetchJob } from '../api'
import type { JobResponse } from '../types'
import { FormattedResult } from './FormattedResult'
import { JsonBlock } from './JsonBlock'

interface JobPollerProps {
  job: JobResponse
  onJobUpdate?: (job: JobResponse) => void
}

const POLL_INTERVAL_MS = 2000
const TERMINAL_STATUSES = new Set(['completed', 'failed'])

export function JobPoller({ job: initialJob, onJobUpdate }: JobPollerProps) {
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
      <div className="job-status-row">
        <span className="field-label">Job ID:</span> <code>{job.job_id}</code>
      </div>
      <div className="job-status-row">
        <span className="field-label">Status:</span>{' '}
        <span className={`status-badge ${statusClass}`}>{job.status}</span>
        {!isTerminal && !pollError && <span className="spinner" />}
      </div>

      {pollError && <JsonBlock title="Polling Error" value={{ error: pollError }} />}

      {job.status === 'failed' && job.error && <JsonBlock title="Job Error" value={{ error: job.error }} />}

      {job.status === 'completed' && job.result && (
        <FormattedResult title="Job Result" value={job.result} />
      )}
    </div>
  )
}
