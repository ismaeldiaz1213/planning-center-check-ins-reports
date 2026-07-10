import { useLanguage } from '../i18n/LanguageContext'
import styles from './Footer.module.css'

export default function Footer() {
  const { t } = useLanguage()

  return (
    <footer className={styles.footer}>
      <img src="/logo.png" alt="Church Logo" className={styles.logo} />
      <div className={styles.name}>{t('footer.church')}</div>
      <div className={styles.sub}>{t('footer.location')}</div>
    </footer>
  )
}
