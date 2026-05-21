import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LogsModal from '../LogsModal'
import { renderWithProviders } from '../../test/helpers'

vi.mock('../../api/client', () => ({
  fetchJobs: vi.fn(),
}))

import { fetchJobs } from '../../api/client'

const NOW = new Date().toISOString()
const MOCK_JOBS = [
  {
    id: 'job-1',
    type: 'rutas',
    status: 'success',
    output: ['Fetching check-ins…', 'Done.'],
    total_lines: 2,
    started_at: NOW,
    finished_at: NOW,
  },
  {
    id: 'job-2',
    type: 'escuela',
    status: 'failed',
    output: ['Error: network timeout'],
    total_lines: 1,
    started_at: NOW,
    finished_at: NOW,
  },
  {
    id: 'job-3',
    type: 'preview',
    status: 'running',
    output: [],
    total_lines: 0,
    started_at: NOW,
    finished_at: null,
  },
]

describe('LogsModal', () => {
  beforeEach(() => {
    vi.mocked(fetchJobs).mockResolvedValue({ jobs: MOCK_JOBS })
  })

  it('renders the title', () => {
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    expect(screen.getByText('Registros de Trabajos')).toBeInTheDocument()
  })

  it('shows the empty state when there are no jobs', async () => {
    vi.mocked(fetchJobs).mockResolvedValue({ jobs: [] })
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/no se han ejecutado trabajos/i)).toBeInTheDocument()
    })
  })

  it('renders a card for each job', async () => {
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText('Rutas')).toBeInTheDocument()
      expect(screen.getByText('Escuela Dominical')).toBeInTheDocument()
      expect(screen.getByText('Vista Previa')).toBeInTheDocument()
    })
  })

  it('renders status badges for each job', async () => {
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/completado/i)).toBeInTheDocument()
      expect(screen.getByText(/error/i)).toBeInTheDocument()
      expect(screen.getByText(/ejecutando/i)).toBeInTheDocument()
    })
  })

  it('output is hidden by default (collapsed)', async () => {
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Rutas'))
    expect(screen.queryByText('Fetching check-ins…')).not.toBeInTheDocument()
  })

  it('expands job output when a card is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Rutas'))

    const rutasCard = screen.getByText('Rutas').closest('button')!
    await user.click(rutasCard)
    expect(screen.getByText('Fetching check-ins…')).toBeInTheDocument()
    expect(screen.getByText('Done.')).toBeInTheDocument()
  })

  it('collapses output when the same card is clicked again', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Rutas'))

    const rutasCard = screen.getByText('Rutas').closest('button')!
    await user.click(rutasCard)
    expect(screen.getByText('Fetching check-ins…')).toBeInTheDocument()

    await user.click(rutasCard)
    expect(screen.queryByText('Fetching check-ins…')).not.toBeInTheDocument()
  })

  it('shows "Sin salida." for jobs with no output', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Vista Previa'))

    const previewCard = screen.getByText('Vista Previa').closest('button')!
    await user.click(previewCard)
    expect(screen.getByText('Sin salida.')).toBeInTheDocument()
  })

  it('re-fetches jobs when Refresh is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LogsModal onClose={vi.fn()} />)
    await waitFor(() => screen.getByText('Rutas'))

    vi.mocked(fetchJobs).mockResolvedValue({ jobs: [] })
    await user.click(screen.getByRole('button', { name: /actualizar/i }))
    await waitFor(() => {
      expect(screen.getByText(/no se han ejecutado trabajos/i)).toBeInTheDocument()
    })
  })

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    renderWithProviders(<LogsModal onClose={handleClose} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(handleClose).toHaveBeenCalledOnce()
  })
})
