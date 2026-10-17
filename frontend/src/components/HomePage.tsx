import { useLanguage } from '../i18n/LanguageContext'
import type { ActiveModal } from '../App'
import type { Report } from '../types'
import TileCard from './TileCard'
import styles from './HomePage.module.css'
import type { TranslationKey } from '../i18n/translations'

interface Props {
  onOpen:         (modal: ActiveModal) => void
  reports:        Report[]
  reportsLoading: boolean
  reportsError:   string | null
}

type TileDef = {
  id:     ActiveModal
  icon:   string
  tKey:   { title: TranslationKey; desc: TranslationKey }
  active: boolean
}

// Fixed panels shown before the report tiles.
const LEADING_TILES: TileDef[] = [
  { id: 'previews', icon: '📄', active: true, tKey: { title: 'tile.previews.title', desc: 'tile.previews.desc' } },
]

// Fixed panels shown after the report tiles.
const TRAILING_TILES: TileDef[] = [
  { id: 'settings', icon: '⚙️', active: true,  tKey: { title: 'tile.settings.title', desc: 'tile.settings.desc' } },
  { id: null,       icon: '⬆️', active: false, tKey: { title: 'tile.upload.title',   desc: 'tile.upload.desc'   } },
  { id: 'logs',     icon: '📋', active: true,  tKey: { title: 'tile.logs.title',     desc: 'tile.logs.desc'     } },
]

export default function HomePage({ onOpen, reports, reportsLoading, reportsError }: Props) {
  const { t, tOr } = useLanguage()

  const renderFixed = (tile: TileDef, key: string) => (
    <TileCard
      key={key}
      icon={tile.icon}
      title={t(tile.tKey.title)}
      description={t(tile.tKey.desc)}
      active={tile.active}
      onClick={tile.active && tile.id ? () => onOpen(tile.id) : undefined}
    />
  )

  return (
    <main className={styles.main}>
      <h1 className={styles.heading}>{t('home.heading')}</h1>
      <p className={styles.sub}>{t('home.sub')}</p>
      {reportsError && <p className={styles.sub}>{reportsError}</p>}
      <div className={styles.grid}>
        {LEADING_TILES.map((tile, i) => renderFixed(tile, `lead-${i}`))}

        {/* One tile per report in reports.yaml. A report with no translation
            keys falls back to the label and icon the backend supplies. */}
        {!reportsLoading && reports.map(report => (
          <TileCard
            key={report.id}
            icon={report.icon}
            title={tOr(`tile.${report.id}.title`, report.label)}
            description={tOr(`tile.${report.id}.desc`, t('tile.report.desc'))}
            active={true}
            onClick={() => onOpen(report.id)}
          />
        ))}

        {TRAILING_TILES.map((tile, i) => renderFixed(tile, `trail-${i}`))}
      </div>
    </main>
  )
}
