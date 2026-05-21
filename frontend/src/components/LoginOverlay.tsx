import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import styles from './LoginOverlay.module.css'

export default function LoginOverlay() {
  const { login } = useAuth()
  const { t } = useLanguage()

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <h1 className={styles.title}>{t('login.title')}</h1>
        <p className={styles.subtitle}>{t('login.subtitle')}</p>
        <div className={styles.buttonWrapper}>
          <GoogleLogin
            onSuccess={(resp) => { if (resp.credential) login(resp.credential) }}
            onError={() => {}}
          />
        </div>
        <p className={styles.hint}>{t('login.hint')}</p>
      </div>
    </div>
  )
}
