import { useLanguage } from '../i18n/LanguageContext'
import type { ActiveModal } from '../App'
import TileCard from './TileCard'
import styles from './HomePage.module.css'
import type { TranslationKey } from '../i18n/translations'

interface Props {
  onOpen: (modal: ActiveModal) => void
}

type TileDef = {
  id:    ActiveModal
  icon:  string
  tKey:  { title: TranslationKey; desc: TranslationKey }
  active: boolean
}

const TILES: TileDef[] = [
  { id: 'previews', icon: '📄', active: true,  tKey: { title: 'tile.previews.title', desc: 'tile.previews.desc' } },
  { id: 'rutas',    icon: '🚌', active: true,  tKey: { title: 'tile.rutas.title',    desc: 'tile.rutas.desc'    } },
  { id: 'escuela',  icon: '📚', active: true,  tKey: { title: 'tile.escuela.title',  desc: 'tile.escuela.desc'  } },
  { id: null,       icon: '⚙️', active: false, tKey: { title: 'tile.settings.title', desc: 'tile.settings.desc' } },
  { id: null,       icon: '⬆️', active: false, tKey: { title: 'tile.upload.title',   desc: 'tile.upload.desc'   } },
  { id: null,       icon: '📋', active: false, tKey: { title: 'tile.logs.title',     desc: 'tile.logs.desc'     } },
]

export default function HomePage({ onOpen }: Props) {
  const { t } = useLanguage()

  return (
    <main className={styles.main}>
      <h1 className={styles.heading}>{t('home.heading')}</h1>
      <p className={styles.sub}>{t('home.sub')}</p>
      <div className={styles.grid}>
        {TILES.map((tile, i) => (
          <TileCard
            key={i}
            icon={tile.icon}
            title={t(tile.tKey.title)}
            description={t(tile.tKey.desc)}
            active={tile.active}
            onClick={tile.active && tile.id ? () => onOpen(tile.id) : undefined}
          />
        ))}
      </div>
    </main>
  )
}
