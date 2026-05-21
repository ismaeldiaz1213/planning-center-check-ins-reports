import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PreviewModal from '../PreviewModal'
import { renderWithProviders } from '../../test/helpers'

vi.mock('../../api/client', () => ({
  fetchPreviews: vi.fn(),
  generatePreview: vi.fn(),
}))

vi.mock('../../hooks/useJob', () => ({
  useJob: vi.fn(() => ({ job: null, lines: [] })),
}))

import { fetchPreviews, generatePreview } from '../../api/client'

const MOCK_PREVIEWS = [
  { filename: 'default_Roster.pdf',             theme: 'default',   type: 'roster',       size_bytes: 1000, url: '/previews/default_Roster.pdf' },
  { filename: 'default_Escuela-Roster.pdf',     theme: 'default',   type: 'escuela',      size_bytes: 2000, url: '/previews/default_Escuela-Roster.pdf' },
  { filename: 'primavera_Roster.pdf',           theme: 'primavera', type: 'roster',       size_bytes: 1500, url: '/previews/primavera_Roster.pdf' },
]

describe('PreviewModal', () => {
  beforeEach(() => {
    vi.mocked(fetchPreviews).mockResolvedValue({ previews: MOCK_PREVIEWS })
    vi.mocked(generatePreview).mockResolvedValue({ job_id: 'job-123' })
  })

  it('renders the modal title', async () => {
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    expect(screen.getByText('Vista Previa de PDFs')).toBeInTheDocument()
  })

  it('renders all five season tabs with translations', async () => {
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Predeterminado' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Primavera' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Verano' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Otoño' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Invierno' })).toBeInTheDocument()
  })

  it('renders all three pdf type buttons with translations', () => {
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Roster' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Escuela' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Direcciones' })).toBeInTheDocument()
  })

  it('renders the Regenerate button', () => {
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    expect(screen.getByRole('button', { name: /regenerar/i })).toBeInTheDocument()
  })

  it('shows the PDF iframe when a matching preview is found', async () => {
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    // Default theme + roster type should find default_Roster.pdf
    await waitFor(() => {
      expect(screen.getByTitle('default_Roster.pdf')).toBeInTheDocument()
    })
  })

  it('shows the empty state when no matching preview exists', async () => {
    vi.mocked(fetchPreviews).mockResolvedValue({ previews: [] })
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByText(/no se encontró pdf para/i)).toBeInTheDocument()
    })
  })

  it('calls generatePreview when Regenerate is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /regenerar/i }))
    expect(generatePreview).toHaveBeenCalledWith({ theme: undefined, type: 'roster' })
  })

  it('calls generatePreview with theme when a seasonal tab is active', async () => {
    const user = userEvent.setup()
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Primavera' }))
    await user.click(screen.getByRole('button', { name: /regenerar/i }))
    expect(generatePreview).toHaveBeenCalledWith({ theme: 'primavera', type: 'roster' })
  })

  it('switches iframe src when pdf type button is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<PreviewModal onClose={vi.fn()} />)
    await waitFor(() => expect(screen.getByTitle('default_Roster.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Escuela' }))
    await waitFor(() => {
      expect(screen.getByTitle('default_Escuela-Roster.pdf')).toBeInTheDocument()
    })
  })

  it('calls onClose when the close button is clicked', async () => {
    const user = userEvent.setup()
    const handleClose = vi.fn()
    renderWithProviders(<PreviewModal onClose={handleClose} />)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(handleClose).toHaveBeenCalledOnce()
  })
})
