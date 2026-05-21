import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HomePage from '../HomePage'
import { renderWithProviders } from '../../test/helpers'

describe('HomePage', () => {
  it('renders the dashboard heading in Spanish', () => {
    renderWithProviders(<HomePage onOpen={vi.fn()} />)
    expect(screen.getByText('Panel Principal')).toBeInTheDocument()
  })

  it('renders all six tile headings', () => {
    renderWithProviders(<HomePage onOpen={vi.fn()} />)
    expect(screen.getByText('Vista Previa de PDFs')).toBeInTheDocument()
    expect(screen.getByText('Ejecutar Rutas')).toBeInTheDocument()
    expect(screen.getByText('Ejecutar Escuela Dominical')).toBeInTheDocument()
    expect(screen.getByText('Editar Configuración')).toBeInTheDocument()
    expect(screen.getByText('Subir Código')).toBeInTheDocument()
    expect(screen.getByText('Ver Registros')).toBeInTheDocument()
  })

  it('has 5 active tiles (Upload is Coming Soon)', () => {
    renderWithProviders(<HomePage onOpen={vi.fn()} />)
    const ctaButtons = screen.getAllByText('Abrir →')
    expect(ctaButtons).toHaveLength(5)
    expect(screen.getAllByText('Próximamente')).toHaveLength(1)
  })

  it('calls onOpen with "previews" when PDF Previews tile is clicked', async () => {
    const user = userEvent.setup()
    const handleOpen = vi.fn()
    renderWithProviders(<HomePage onOpen={handleOpen} />)
    // First active tile is Previews
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[0])
    expect(handleOpen).toHaveBeenCalledWith('previews')
  })

  it('calls onOpen with "rutas" when Rutas tile is clicked', async () => {
    const user = userEvent.setup()
    const handleOpen = vi.fn()
    renderWithProviders(<HomePage onOpen={handleOpen} />)
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[1])
    expect(handleOpen).toHaveBeenCalledWith('rutas')
  })

  it('calls onOpen with "escuela" when Escuela tile is clicked', async () => {
    const user = userEvent.setup()
    const handleOpen = vi.fn()
    renderWithProviders(<HomePage onOpen={handleOpen} />)
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[2])
    expect(handleOpen).toHaveBeenCalledWith('escuela')
  })

  it('calls onOpen with "settings" when Settings tile is clicked', async () => {
    const user = userEvent.setup()
    const handleOpen = vi.fn()
    renderWithProviders(<HomePage onOpen={handleOpen} />)
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[3])
    expect(handleOpen).toHaveBeenCalledWith('settings')
  })

  it('calls onOpen with "logs" when Logs tile is clicked', async () => {
    const user = userEvent.setup()
    const handleOpen = vi.fn()
    renderWithProviders(<HomePage onOpen={handleOpen} />)
    const buttons = screen.getAllByRole('button')
    await user.click(buttons[4])
    expect(handleOpen).toHaveBeenCalledWith('logs')
  })
})
