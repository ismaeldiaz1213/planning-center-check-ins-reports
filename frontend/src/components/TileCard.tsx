import { useLanguage } from '../i18n/LanguageContext'
import styles from './TileCard.module.css'

interface Props {
  icon:        string
  title:       string
  description: string
  active:      boolean
  onClick?:    () => void
}

export default function TileCard({ icon, title, description, active, onClick }: Props) {
  const { t } = useLanguage()
  const cls = [styles.card, active ? styles.active : styles.disabled].join(' ')

  return (
    <div
      className={cls}
      onClick={active ? onClick : undefined}
      role={active ? 'button' : undefined}
      tabIndex={active ? 0 : -1}
      onKeyDown={active && onClick ? e => e.key === 'Enter' && onClick() : undefined}
    >
      <div className={styles.iconWrap}>
        <span className={styles.icon}>{icon}</span>
      </div>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.desc}>{description}</p>
      {active
        ? <span className={styles.cta}>{t('tile.cta')}</span>
        : <span className={styles.soon}>{t('tile.soon')}</span>
      }
    </div>
  )
}
