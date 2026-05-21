import { useLanguage } from '../i18n/LanguageContext'
import styles from './Footer.module.css'

export default function Footer() {
  const { t } = useLanguage()

  return (
    <footer className={styles.footer}>
      <img src="/ibl_logo.png" alt="IBL Logo" className={styles.logo} />
      <div className={styles.name}>{t('footer.church')}</div>
      <div className={styles.sub}>{t('footer.location')}</div>
    </footer>
  )
}
