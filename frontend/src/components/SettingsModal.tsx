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
        rutas_weeks:                   form.rutas_weeks,
        rutas_theme:                   form.rutas_theme,
        escuela_weeks:                 form.escuela_weeks,
        escuela_theme:                 form.escuela_theme,
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

              {/* Rutas defaults */}
              <section className={sStyles.section}>
                <h3 className={sStyles.sectionTitle}>{t('settings.section.rutas')}</h3>
                <div className={sStyles.row}>
                  <div className={sStyles.field}>
                    <label className={sStyles.label}>{t('settings.weeks')}</label>
                    <input
                      className={`${sStyles.input} ${sStyles.narrow}`}
                      type="number"
                      min={1} max={52}
                      value={form.rutas_weeks}
                      onChange={e => set('rutas_weeks', Number(e.target.value))}
                    />
                  </div>
                  <div className={sStyles.field}>
                    <label className={sStyles.label}>{t('settings.theme')}</label>
                    <select
                      className={sStyles.select}
                      value={form.rutas_theme}
                      onChange={e => set('rutas_theme', e.target.value)}
                    >
                      <option value="">{t('settings.theme.none')}</option>
                      {THEMES.map(th => (
                        <option key={th} value={th}>{t(`preview.theme.${th}` as any)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>

              {/* Escuela defaults */}
              <section className={sStyles.section}>
                <h3 className={sStyles.sectionTitle}>{t('settings.section.escuela')}</h3>
                <div className={sStyles.row}>
                  <div className={sStyles.field}>
                    <label className={sStyles.label}>{t('settings.weeks')}</label>
                    <input
                      className={`${sStyles.input} ${sStyles.narrow}`}
                      type="number"
                      min={1} max={52}
                      value={form.escuela_weeks}
                      onChange={e => set('escuela_weeks', Number(e.target.value))}
                    />
                  </div>
                  <div className={sStyles.field}>
                    <label className={sStyles.label}>{t('settings.theme')}</label>
                    <select
                      className={sStyles.select}
                      value={form.escuela_theme}
                      onChange={e => set('escuela_theme', e.target.value)}
                    >
                      <option value="">{t('settings.theme.none')}</option>
                      {THEMES.map(th => (
                        <option key={th} value={th}>{t(`preview.theme.${th}` as any)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </section>
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
