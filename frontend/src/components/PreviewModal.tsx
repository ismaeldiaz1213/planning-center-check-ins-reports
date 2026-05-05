import { useEffect, useRef, useState } from 'react'
import { fetchPreviews, generatePreview } from '../api/client'
import { useJob } from '../hooks/useJob'
import { useLanguage } from '../i18n/LanguageContext'
import type { Preview } from '../types'
import StatusBadge from './StatusBadge'
import styles from './Modal.module.css'
import pStyles from './PreviewModal.module.css'

interface Props {
  onClose: () => void
}

const THEMES = [
  { key: 'default',   label: 'Default'   },
  { key: 'primavera', label: 'Primavera' },
  { key: 'verano',    label: 'Verano'    },
  { key: 'otono',     label: 'Otoño'     },
  { key: 'invierno',  label: 'Invierno'  },
]

const PDF_TYPES = [
  { key: 'roster',      label: 'Roster'      },
  { key: 'escuela',     label: 'Escuela'     },
  { key: 'direcciones', label: 'Direcciones' },
]

export default function PreviewModal({ onClose }: Props) {
  const { t }                               = useLanguage()
  const [previews, setPreviews]             = useState<Preview[]>([])
  const [theme, setTheme]                   = useState('default')
  const [pdfType, setPdfType]               = useState('roster')
  const [jobId, setJobId]                   = useState<string | null>(null)
  const [error, setError]                   = useState<string | null>(null)
  const { job }                             = useJob(jobId)
  const iframeRef                           = useRef<HTMLIFrameElement>(null)

  const load = () =>
    fetchPreviews().then(d => setPreviews(d.previews)).catch(() => {})

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (job?.status === 'success') load()
  }, [job?.status])

  const selected    = previews.find(p => p.theme === theme && p.type === pdfType)
  const genStatus   = (job?.status ?? 'idle') as 'idle' | 'running' | 'success' | 'failed'
  const isGenerating = genStatus === 'running'

  useEffect(() => {
    if (iframeRef.current && selected) {
      iframeRef.current.src = selected.url + '?t=' + Date.now()
    }
  }, [selected?.url, job?.status])

  const handleRegenerate = async () => {
    setError(null)
    try {
      const res = await generatePreview({
        theme: theme === 'default' ? undefined : theme,
        type:  pdfType,
      })
      setJobId(res.job_id)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`${styles.modal} ${styles.previewModal}`}>

        <div className={styles.header}>
          <div className={styles.headerTitle}>{t('preview.title')}</div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        {/* Theme tabs */}
        <div className={pStyles.tabs}>
          {THEMES.map(th => (
            <button
              key={th.key}
              className={`${pStyles.tab} ${theme === th.key ? pStyles.tabActive : ''}`}
              onClick={() => setTheme(th.key)}
            >
              {th.label}
            </button>
          ))}
        </div>

        {/* Type selector + regenerate */}
        <div className={pStyles.controls}>
          <div className={pStyles.typeGroup}>
            {PDF_TYPES.map(tp => (
              <button
                key={tp.key}
                className={`${pStyles.typeBtn} ${pdfType === tp.key ? pStyles.typeBtnActive : ''}`}
                onClick={() => setPdfType(tp.key)}
              >
                {tp.label}
              </button>
            ))}
          </div>
          <div className={pStyles.genGroup}>
            <button
              className={styles.runBtn}
              onClick={handleRegenerate}
              disabled={isGenerating}
            >
              {isGenerating ? t('preview.generating') : t('preview.regenerate')}
            </button>
            <StatusBadge status={genStatus} />
            {error && <span className={styles.errorText}>{error}</span>}
          </div>
        </div>

        {/* PDF iframe */}
        <div className={pStyles.viewer}>
          {selected ? (
            <iframe
              ref={iframeRef}
              src={selected.url}
              title={selected.filename}
              className={pStyles.iframe}
            />
          ) : (
            <div className={pStyles.empty}>
              <span>{t('preview.empty')} <strong>{theme}</strong> / <strong>{pdfType}</strong></span>
              <span className={pStyles.emptyHint}>{t('preview.emptyHint')}</span>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
