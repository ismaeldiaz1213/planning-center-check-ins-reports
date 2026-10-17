import { useEffect, useState } from 'react'
import { fetchReports } from '../api/client'
import type { Report } from '../types'

/**
 * Loads the reports configured in the backend's reports.yaml.
 *
 * The dashboard renders one tile per report, so adding a report to reports.yaml
 * is enough to make it appear here — no frontend change required.
 */
export function useReports() {
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchReports()
      .then(data => { if (!cancelled) setReports(data.reports ?? []) })
      .catch(e => { if (!cancelled) setError(String(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return { reports, loading, error }
}
