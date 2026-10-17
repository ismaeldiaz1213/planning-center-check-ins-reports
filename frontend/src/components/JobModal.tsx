import { useEffect, useRef, useState } from 'react'
import { runJob } from '../api/client'
import { useJob } from '../hooks/useJob'
import { useLanguage } from '../i18n/LanguageContext'
import StatusBadge from './StatusBadge'
import styles from './Modal.module.css'

import type { Report } from '../types'

interface Props {
  report:  Report
  onClose: () => void
}

export default function JobModal({ report, onClose }: Props) {
  const { t, tOr } = useLanguage()
  const [jobId, setJobId]   = useState<string | null>(null)
  const [error, setError]   = useState<string | null>(null)
  const { job, lines }      = useJob(jobId)
  const terminalRef         = useRef<HTMLDivElement>(null)

  // Reports configured in reports.yaml may have no translation keys; fall back
  // to the label the backend supplies.
  const title = tOr(`job.${report.id}.title`, report.label)
  const desc  = tOr(`job.${report.id}.desc`, t('job.report.desc'))
  const status = (job?.status ?? 'idle') as 'idle' | 'running' | 'success' | 'failed'
  const isRunning = status === 'running'

  useEffect(() => {
    const el = terminalRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines])

  const handleRun = async () => {
    setError(null)
    try {
      const res = await runJob(report.id)
      setJobId(res.job_id)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`${styles.modal} ${styles.jobModal}`}>

        <div className={styles.header}>
          <div>
            <div className={styles.headerTitle}>{title}</div>
            <div className={styles.headerSub}>{desc}</div>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div ref={terminalRef} className={`${styles.terminal} terminal`}>
          {lines.length === 0 && !isRunning && (
            <span className={styles.termPlaceholder}>{t('job.placeholder')}</span>
          )}
          {lines.map((line, i) => (
            <div key={i} className={styles.termLine}>{line || ' '}</div>
          ))}
        </div>

        <div className={styles.footer}>
          <button className={styles.runBtn} onClick={handleRun} disabled={isRunning}>
            {isRunning ? t('job.running') : t('job.run')}
          </button>
          <StatusBadge status={status} />
          {error && <span className={styles.errorText}>{error}</span>}
        </div>

      </div>
    </div>
  )
}
