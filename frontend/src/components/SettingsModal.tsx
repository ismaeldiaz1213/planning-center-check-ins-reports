import { useEffect, useState } from 'react'
import { fetchSettings, saveSettings } from '../api/client'
import { useLanguage } from '../i18n/LanguageContext'
import type { Settings } from '../types'
import styles from './Modal.module.css'
import sStyles from './SettingsModal.module.css'

interface Props {
  onClose: () => void
}

const THEMES = ['primavera', 'verano', 'otono', 'invierno'] as const

export default function SettingsModal({ onClose }: Props) {
  const { t } = useLanguage()
  const [form, setForm]       = useState<Settings | null>(null)
  const [saving, setSaving]   = useState(false)
  const [saved, setSaved]     = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [showSecret, setShowSecret] = useState(false)

  useEffect(() => {
    fetchSettings().then(setForm).catch(e => setError(String(e)))
  }, [])

  const set = <K extends keyof Settings>(key: K, val: Settings[K]) =>
    setForm(f => f ? { ...f, [key]: val } : f)

  /** Update one field of one report's run defaults. */
  const setReport = (id: string, patch: { weeks?: number; theme?: string }) =>
    setForm(f => f
      ? { ...f, reports: { ...f.reports, [id]: { ...f.reports[id], ...patch } } }
      : f)

  const handleSave = async () => {
    if (!form) return
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await saveSettings({
        pco_app_id:                    form.pco_app_id,
        pco_secret:                    form.pco_secret,
        google_drive_parent_folder_id: form.google_drive_parent_folder_id,
        reports: Object.fromEntries(
          Object.entries(form.reports).map(([id, r]) => [id, { weeks: r.weeks, theme: r.theme }])
        ),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={`${styles.modal} ${styles.settingsModal}`}>

        <div className={styles.header}>
          <div className={styles.headerTitle}>{t('settings.title')}</div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className={sStyles.body}>
          {!form ? (
            <div className={sStyles.loading}>{error ?? 'Loading…'}</div>
          ) : (
            <>
              {/* PCO Credentials */}
              <section className={sStyles.section}>
                <h3 className={sStyles.sectionTitle}>{t('settings.section.creds')}</h3>
                <div className={sStyles.field}>
                  <label className={sStyles.label}>{t('settings.pco_app_id')}</label>
                  <input
                    className={sStyles.input}
                    type="text"
                    value={form.pco_app_id}
                    onChange={e => set('pco_app_id', e.target.value)}
                    spellCheck={false}
                  />
                </div>
                <div className={sStyles.field}>
                  <label className={sStyles.label}>{t('settings.pco_secret')}</label>
                  <div className={sStyles.passwordRow}>
                    <input
                      className={sStyles.input}
                      type={showSecret ? 'text' : 'password'}
                      value={form.pco_secret}
                      onChange={e => set('pco_secret', e.target.value)}
                      spellCheck={false}
                    />
                    <button
                      className={sStyles.toggleBtn}
                      onClick={() => setShowSecret(s => !s)}
                      type="button"
                    >
                      {showSecret ? '🙈' : '👁️'}
                    </button>
                  </div>
                </div>
              </section>

              {/* Google Drive */}
              <section className={sStyles.section}>
                <h3 className={sStyles.sectionTitle}>{t('settings.section.drive')}</h3>
                <div className={sStyles.field}>
                  <label className={sStyles.label}>{t('settings.drive_folder')}</label>
                  <input
                    className={sStyles.input}
                    type="text"
                    value={form.google_drive_parent_folder_id}
                    onChange={e => set('google_drive_parent_folder_id', e.target.value)}
                    spellCheck={false}
                  />
                </div>
              </section>

              {/* One run-defaults section per report configured in reports.yaml */}
              {Object.entries(form.reports).map(([id, report]) => (
                <section className={sStyles.section} key={id}>
                  <h3 className={sStyles.sectionTitle}>
                    {`${report.label} — ${t('settings.section.report')}`}
                  </h3>
                  <div className={sStyles.row}>
                    <div className={sStyles.field}>
                      <label className={sStyles.label} htmlFor={`weeks-${id}`}>
                        {t('settings.weeks')}
                      </label>
                      <input
                        id={`weeks-${id}`}
                        className={`${sStyles.input} ${sStyles.narrow}`}
                        type="number"
                        min={1} max={52}
                        value={report.weeks}
                        onChange={e => setReport(id, { weeks: Number(e.target.value) })}
                      />
                    </div>
                    <div className={sStyles.field}>
                      <label className={sStyles.label} htmlFor={`theme-${id}`}>
                        {t('settings.theme')}
                      </label>
                      <select
                        id={`theme-${id}`}
                        className={sStyles.select}
                        value={report.theme}
                        onChange={e => setReport(id, { theme: e.target.value })}
                      >
                        <option value="">{t('settings.theme.none')}</option>
                        {THEMES.map(th => (
                          <option key={th} value={th}>{t(`preview.theme.${th}` as any)}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </section>
              ))}
            </>
          )}
        </div>

        <div className={styles.footer}>
          <button
            className={styles.runBtn}
            onClick={handleSave}
            disabled={saving || !form}
          >
            {saving ? t('settings.saving') : saved ? t('settings.saved') : t('settings.save')}
          </button>
          {error && <span className={styles.errorText}>{error}</span>}
        </div>

      </div>
    </div>
  )
}
