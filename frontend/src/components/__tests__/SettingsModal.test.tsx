import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SettingsModal from '../SettingsModal'
import { renderWithProviders } from '../../test/helpers'

vi.mock('../../api/client', () => ({
  fetchSettings: vi.fn(),
  saveSettings: vi.fn(),
}))

import { fetchSettings, saveSettings } from '../../api/client'
import type { Settings } from '../../types'

const MOCK_SETTINGS: Settings = {
  pco_app_id: 'app-id-123',
  pco_secret: 'secret-456',
  google_drive_parent_folder_id: 'folder-789',
  // Run defaults are keyed by report id — one section is rendered per entry.
  reports: {
    rutas:       { label: 'Rutas',                  weeks: 5, theme: ''          },
    escuela:     { label: 'Escuela Dominical',      weeks: 4, theme: 'primavera' },
    'escuela-b': { label: '"B" Escuela Dominical',  weeks: 6, theme: ''          },
  },
}

describe('SettingsModal', () => {
  beforeEach(() => {
    vi.mocked(fetchSettings).mockResolvedValue(MOCK_SETTINGS)
    vi.mocked(saveSettings).mockResolvedValue({ ok: true })
  })

  it('renders the Settings title', () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    expect(screen.getByText('Editar Configuración')).toBeInTheDocument()
  })

  it('loads and displays PCO App ID', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('app-id-123')).toBeInTheDocument()
    })
  })

  it('loads and displays PCO Secret (masked by default)', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      const secretInput = screen.getByDisplayValue('secret-456')
      expect(secretInput).toHaveAttribute('type', 'password')
    })
  })

  it('toggles PCO Secret visibility when the eye button is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByDisplayValue('secret-456'))
    const secretInput = screen.getByDisplayValue('secret-456')
    expect(secretInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByRole('button', { name: '👁️' }))
    expect(secretInput).toHaveAttribute('type', 'text')
  })

  it('loads and displays Google Drive folder ID', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('folder-789')).toBeInTheDocument()
    })
  })

  it('renders section headings', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('Credenciales PCO')).toBeInTheDocument()
      expect(screen.getByText('Google Drive')).toBeInTheDocument()
      expect(screen.getByText('Rutas — Valores por Defecto')).toBeInTheDocument()
      expect(screen.getByText('Escuela Dominical — Valores por Defecto')).toBeInTheDocument()
      expect(screen.getByText('"B" Escuela Dominical — Valores por Defecto')).toBeInTheDocument()
    })
  })

  it('displays one week-count input per report, with loaded values', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('5')).toBeInTheDocument()
      expect(screen.getByDisplayValue('4')).toBeInTheDocument()
      expect(screen.getByDisplayValue('6')).toBeInTheDocument()
    })
  })

  it('renders a section for a report it has never seen before', async () => {
    vi.mocked(fetchSettings).mockResolvedValue({
      ...MOCK_SETTINGS,
      reports: { ninos: { label: 'Clases de Niños', weeks: 3, theme: '' } },
    })
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('Clases de Niños — Valores por Defecto')).toBeInTheDocument()
    })
  })

  it('edits one report\'s weeks without touching the others', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByDisplayValue('6'))

    const input = screen.getByLabelText('Semanas recientes a incluir', { selector: '#weeks-escuela-b' })
    await user.clear(input)
    await user.type(input, '8')
    await user.click(screen.getByRole('button', { name: /guardar$/i }))

    await waitFor(() => {
      const calls = vi.mocked(saveSettings).mock.calls
      const body = calls[calls.length - 1][0]
      expect(body.reports!['escuela-b'].weeks).toBe(8)
      expect(body.reports!.rutas.weeks).toBe(5)
    })
  })

  it('calls saveSettings with current form values when Save is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByDisplayValue('app-id-123'))

    await user.click(screen.getByRole('button', { name: /guardar$/i }))
    await waitFor(() => {
      expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({
        pco_app_id: 'app-id-123',
        pco_secret: 'secret-456',
        google_drive_parent_folder_id: 'folder-789',
        reports: {
          rutas:       { weeks: 5, theme: ''          },
          escuela:     { weeks: 4, theme: 'primavera' },
          'escuela-b': { weeks: 6, theme: ''          },
        },
      }))
    })
  })

  it('shows "¡Guardado!" after a successful save', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByDisplayValue('app-id-123'))
    await user.click(screen.getByRole('button', { name: /guardar$/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /guardado/i })).toBeInTheDocument()
    })
  })

  it('shows an error message when saveSettings rejects', async () => {
    vi.mocked(saveSettings).mockRejectedValue(new Error('Write failed'))
    const user = userEvent.setup()
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByDisplayValue('app-id-123'))
    await user.click(screen.getByRole('button', { name: /guardar$/i }))
    await waitFor(() => {
      expect(screen.getByText(/write failed/i)).toBeInTheDocument()
    })
  })

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    renderWithProviders(<SettingsModal onClose={handleClose} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(handleClose).toHaveBeenCalledOnce()
  })
})
