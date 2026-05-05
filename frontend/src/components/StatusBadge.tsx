import { useLanguage } from '../i18n/LanguageContext'
import type { JobStatus } from '../types'

type Status = JobStatus | 'idle'

const COLORS: Record<Status, { bg: string; color: string }> = {
  idle:    { bg: '#E2E8F0', color: '#475569' },
  running: { bg: '#DBEAFE', color: '#1D4ED8' },
  success: { bg: '#DCFCE7', color: '#15803D' },
  failed:  { bg: '#FEE2E2', color: '#B91C1C' },
}

const KEY: Record<Status, 'status.idle' | 'status.running' | 'status.success' | 'status.failed'> = {
  idle:    'status.idle',
  running: 'status.running',
  success: 'status.success',
  failed:  'status.failed',
}

export default function StatusBadge({ status }: { status: Status }) {
  const { t } = useLanguage()
  const { bg, color } = COLORS[status] ?? COLORS.idle

  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 700,
      letterSpacing: '0.4px',
      textTransform: 'uppercase',
      backgroundColor: bg,
      color,
      whiteSpace: 'nowrap',
    }}>
      {t(KEY[status] ?? 'status.idle')}
    </span>
  )
}
