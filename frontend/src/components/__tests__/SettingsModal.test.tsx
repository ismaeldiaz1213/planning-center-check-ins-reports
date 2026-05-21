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

const MOCK_SETTINGS = {
  pco_app_id: 'app-id-123',
  pco_secret: 'secret-456',
  google_drive_parent_folder_id: 'folder-789',
  rutas_weeks: 5,
  rutas_theme: '',
  escuela_weeks: 4,
  escuela_theme: 'primavera',
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
      expect(screen.getByText('Valores por Defecto – Rutas')).toBeInTheDocument()
      expect(screen.getByText('Valores por Defecto – Escuela')).toBeInTheDocument()
    })
  })

  it('displays week count inputs with loaded values', async () => {
    renderWithProviders(<SettingsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByDisplayValue('5')).toBeInTheDocument()
      expect(screen.getByDisplayValue('4')).toBeInTheDocument()
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
        rutas_weeks: 5,
        escuela_weeks: 4,
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
