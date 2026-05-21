import { useCallback, useEffect, useState } from 'react'
import { fetchJobs } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import type { Job } from '../types'
import StatusBadge from './StatusBadge'
import styles from './Modal.module.css'
import lStyles from './LogsModal.module.css'

interface Props {
  onClose: () => void
}

function duration(job: Job): string {
  if (!job.finished_at) return '–'
  const ms = new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60000)  return `${Math.round(diff / 1000)}s ago`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return new Date(iso).toLocaleDateString()
}

export default function LogsModal({ onClose }: Props) {
  const { t } = useLanguage()
  const [jobs, setJobs]         = useState<Job[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchJobs()
      .then(d => setJobs(d.jobs))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const jobTypeLabel = (type: string) => {
    if (type === 'rutas')   return t('logs.type.rutas')
    if (type === 'escuela') return t('logs.type.escuela')
    return t('logs.type.preview')
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`${styles.modal} ${styles.logsModal}`}>

        <div className={styles.header}>
          <div className={styles.headerTitle}>{t('logs.title')}</div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className={lStyles.refreshBtn}
              onClick={load}
              disabled={loading}
            >
              {loading ? '⏳' : '🔄'} {t('logs.refresh')}
            </button>
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
          </div>
        </div>

        <div className={lStyles.body}>
          {error && <div className={lStyles.errorBanner}>{error}</div>}

          {jobs.length === 0 && !loading ? (
            <div className={lStyles.empty}>{t('logs.empty')}</div>
          ) : (
            <div className={lStyles.list}>
              {jobs.map(job => {
                const isOpen = expanded === job.id
                const status = job.status as 'running' | 'success' | 'failed'
                return (
                  <div key={job.id} className={lStyles.card}>
                    <button
                      className={lStyles.cardHeader}
                      onClick={() => setExpanded(isOpen ? null : job.id)}
                    >
                      <div className={lStyles.cardLeft}>
                        <span className={lStyles.jobType}>{jobTypeLabel(job.type)}</span>
                        <span className={lStyles.started}>{timeAgo(job.started_at)}</span>
                        <span className={lStyles.dur}>{duration(job)}</span>
                      </div>
                      <div className={lStyles.cardRight}>
                        <StatusBadge status={status} />
                        <span className={lStyles.chevron}>{isOpen ? '▲' : '▼'}</span>
                      </div>
                    </button>

                    {isOpen && (
                      <div className={lStyles.output}>
                        {job.output.length === 0 ? (
                          <span className={lStyles.noOutput}>{t('logs.noOutput')}</span>
                        ) : (
                          job.output.map((line, i) => (
                            <div key={i} className={lStyles.line}>{line || ' '}</div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
