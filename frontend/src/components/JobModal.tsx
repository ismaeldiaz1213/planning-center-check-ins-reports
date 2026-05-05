import { useEffect, useRef, useState } from 'react'
import { runJob } from '../api/client'
import { useJob } from '../hooks/useJob'
import { useLanguage } from '../i18n/LanguageContext'
import StatusBadge from './StatusBadge'
import styles from './Modal.module.css'

interface Props {
  type:    'rutas' | 'escuela'
  onClose: () => void
}

export default function JobModal({ type, onClose }: Props) {
  const { t } = useLanguage()
  const [jobId, setJobId]   = useState<string | null>(null)
  const [error, setError]   = useState<string | null>(null)
  const { job, lines }      = useJob(jobId)
  const terminalRef         = useRef<HTMLDivElement>(null)

  const titleKey = type === 'rutas' ? 'job.rutas.title' : 'job.escuela.title'
  const descKey  = type === 'rutas' ? 'job.rutas.desc'  : 'job.escuela.desc'
  const status   = (job?.status ?? 'idle') as 'idle' | 'running' | 'success' | 'failed'
  const isRunning = status === 'running'

  useEffect(() => {
    const el = terminalRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines])

  const handleRun = async () => {
    setError(null)
    try {
      const res = await runJob(type)
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
            <div className={styles.headerTitle}>{t(titleKey)}</div>
            <div className={styles.headerSub}>{t(descKey)}</div>
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
