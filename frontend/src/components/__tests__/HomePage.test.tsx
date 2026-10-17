import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HomePage from '../HomePage'
import { renderWithProviders, ALL_REPORTS, makeReport } from '../../test/helpers'

/** HomePage is now driven by the reports the backend reports, so every test
 *  supplies them explicitly. */
function renderHome(onOpen = vi.fn(), reports = ALL_REPORTS) {
  renderWithProviders(
    <HomePage onOpen={onOpen} reports={reports} reportsLoading={false} reportsError={null} />
  )
  return onOpen
}

describe('HomePage', () => {
  it('renders the dashboard heading in Spanish', () => {
    renderHome()
    expect(screen.getByText('Panel Principal')).toBeInTheDocument()
  })

  it('renders a tile per report plus the fixed panels', () => {
    renderHome()
    expect(screen.getByText('Vista Previa de PDFs')).toBeInTheDocument()
    expect(screen.getByText('Ejecutar Rutas')).toBeInTheDocument()
    expect(screen.getByText('Ejecutar Escuela Dominical')).toBeInTheDocument()
    expect(screen.getByText('Ejecutar "B" Escuela Dominical')).toBeInTheDocument()
    expect(screen.getByText('Editar Configuración')).toBeInTheDocument()
    expect(screen.getByText('Subir Código')).toBeInTheDocument()
    expect(screen.getByText('Ver Registros')).toBeInTheDocument()
  })

  it('has one active tile per report plus previews, settings and logs', () => {
    renderHome()
    expect(screen.getAllByText('Abrir →')).toHaveLength(6)
    expect(screen.getAllByText('Próximamente')).toHaveLength(1)
  })

  it('falls back to the backend label for a report with no translation key', () => {
    renderHome(vi.fn(), [makeReport({ id: 'ninos', label: 'Clases de Niños', icon: '🧒' })])
    expect(screen.getByText('Clases de Niños')).toBeInTheDocument()
  })

  it('renders no report tiles while the report list is loading', () => {
    renderWithProviders(
      <HomePage onOpen={vi.fn()} reports={[]} reportsLoading={true} reportsError={null} />
    )
    expect(screen.queryByText('Ejecutar Rutas')).not.toBeInTheDocument()
    expect(screen.getByText('Vista Previa de PDFs')).toBeInTheDocument()
  })

  it('shows an error when the report list fails to load', () => {
    renderWithProviders(
      <HomePage onOpen={vi.fn()} reports={[]} reportsLoading={false} reportsError="Error: boom" />
    )
    expect(screen.getByText('Error: boom')).toBeInTheDocument()
  })

  it('calls onOpen with "previews" when the PDF Previews tile is clicked', async () => {
    const user = userEvent.setup()
    const onOpen = renderHome()
    await user.click(screen.getAllByRole('button')[0])
    expect(onOpen).toHaveBeenCalledWith('previews')
  })

  it.each([
    ['rutas', 1],
    ['escuela', 2],
    ['escuela-b', 3],
  ])('calls onOpen with %s when that report tile is clicked', async (id, index) => {
    const user = userEvent.setup()
    const onOpen = renderHome()
    await user.click(screen.getAllByRole('button')[index])
    expect(onOpen).toHaveBeenCalledWith(id)
  })

  it('calls onOpen with "settings" when the Settings tile is clicked', async () => {
    const user = userEvent.setup()
    const onOpen = renderHome()
    await user.click(screen.getAllByRole('button')[4])
    expect(onOpen).toHaveBeenCalledWith('settings')
  })

  it('calls onOpen with "logs" when the Logs tile is clicked', async () => {
    const user = userEvent.setup()
    const onOpen = renderHome()
    await user.click(screen.getAllByRole('button')[5])
    expect(onOpen).toHaveBeenCalledWith('logs')
  })
})
