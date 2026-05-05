import { useLanguage } from '../i18n/LanguageContext'
import type { Lang } from '../i18n/translations'
import styles from './Navbar.module.css'

export default function Navbar() {
  const { lang, setLang, t } = useLanguage()

  return (
    <nav className={styles.nav}>
      <div className={styles.brand}>
        <span className={styles.title}>{t('nav.title')}</span>
      </div>

      <div className={styles.right}>
        <a className={styles.link} href="#">{t('nav.dashboard')}</a>
        <div className={styles.langToggle} role="group" aria-label="Language">
          {(['es', 'en'] as Lang[]).map(l => (
            <button
              key={l}
              className={`${styles.langBtn} ${lang === l ? styles.langActive : ''}`}
              onClick={() => setLang(l)}
              aria-pressed={lang === l}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </nav>
  )
}
