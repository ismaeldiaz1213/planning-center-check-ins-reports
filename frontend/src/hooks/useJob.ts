import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchJob } from '../api/client'
import type { Job } from '../types'

/**
 * Polls /api/jobs/{jobId}?since=N every second while the job is running.
 * Accumulates output lines locally so the terminal never re-renders stale content.
 * Stops automatically once status transitions to 'success' or 'failed'.
 */
export function useJob(jobId: string | null) {
  const [job, setJob]   = useState<Job | null>(null)
  const [lines, setLines] = useState<string[]>([])
  const sinceRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  const poll = useCallback(async () => {
    if (!jobId) return
    try {
      const data = await fetchJob(jobId, sinceRef.current)
      sinceRef.current = data.total_lines
      if (data.output.length > 0) {
        setLines(prev => [...prev, ...data.output])
      }
      setJob(data)
      if (data.status !== 'running') stopPolling()
    } catch {
      // transient errors — keep retrying
    }
  }, [jobId])

  useEffect(() => {
    if (!jobId) return
    setJob(null)
    setLines([])
    sinceRef.current = 0
    poll()
    timerRef.current = setInterval(poll, 1000)
    return stopPolling
  }, [jobId, poll])

  return { job, lines }
}
