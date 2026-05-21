import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobModal from '../JobModal'
import { renderWithProviders } from '../../test/helpers'

vi.mock('../../api/client', () => ({
  runJob: vi.fn(),
}))

vi.mock('../../hooks/useJob', () => ({
  useJob: vi.fn(() => ({ job: null, lines: [] })),
}))

import { runJob } from '../../api/client'
import { useJob } from '../../hooks/useJob'

describe('JobModal — Rutas', () => {
  beforeEach(() => {
    vi.mocked(runJob).mockResolvedValue({ job_id: 'job-abc' })
    vi.mocked(useJob).mockReturnValue({ job: null, lines: [] })
  })

  it('renders the Rutas title', () => {
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    expect(screen.getByText('Ejecutar Rutas')).toBeInTheDocument()
  })

  it('renders the run button in idle state', () => {
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: /ejecutar$/i })).toBeInTheDocument()
  })

  it('shows the placeholder text before any run', () => {
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    expect(screen.getByText(/presiona ejecutar para comenzar/i)).toBeInTheDocument()
  })

  it('calls runJob("rutas") when Run is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /ejecutar$/i }))
    expect(runJob).toHaveBeenCalledWith('rutas')
  })

  it('disables the Run button while running', () => {
    vi.mocked(useJob).mockReturnValue({
      job: { id: 'job-abc', type: 'rutas', status: 'running', output: [], total_lines: 0, started_at: '', finished_at: null },
      lines: [],
    })
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: /ejecutando/i })).toBeDisabled()
  })

  it('renders terminal output lines when the job produces output', () => {
    vi.mocked(useJob).mockReturnValue({
      job: { id: 'job-abc', type: 'rutas', status: 'success', output: [], total_lines: 2, started_at: '', finished_at: null },
      lines: ['Line one', 'Line two'],
    })
    renderWithProviders(<JobModal type="rutas" onClose={vi.fn()} />)
    expect(screen.getByText('Line one')).toBeInTheDocument()
    expect(screen.getByText('Line two')).toBeInTheDocument()
  })

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    renderWithProviders(<JobModal type="rutas" onClose={handleClose} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(handleClose).toHaveBeenCalledOnce()
  })
})

describe('JobModal — Escuela Dominical', () => {
  beforeEach(() => {
    vi.mocked(runJob).mockResolvedValue({ job_id: 'job-def' })
    vi.mocked(useJob).mockReturnValue({ job: null, lines: [] })
  })

  it('renders the Escuela Dominical title', () => {
    renderWithProviders(<JobModal type="escuela" onClose={vi.fn()} />)
    expect(screen.getByText('Ejecutar Escuela Dominical')).toBeInTheDocument()
  })

  it('calls runJob("escuela") when Run is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<JobModal type="escuela" onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /ejecutar$/i }))
    expect(runJob).toHaveBeenCalledWith('escuela')
  })

  it('shows an error message when runJob rejects', async () => {
    vi.mocked(runJob).mockRejectedValue(new Error('Server error'))
    const user = userEvent.setup()
    renderWithProviders(<JobModal type="escuela" onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /ejecutar$/i }))
    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument()
    })
  })
})
