import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import StatusBadge from '../StatusBadge'
import { renderWithProviders } from '../../test/helpers'

describe('StatusBadge', () => {
  it('renders "Inactivo" for idle status (Spanish default)', () => {
    renderWithProviders(<StatusBadge status="idle" />)
    expect(screen.getByText(/inactivo/i)).toBeInTheDocument()
  })

  it('renders "Ejecutando" for running status', () => {
    renderWithProviders(<StatusBadge status="running" />)
    expect(screen.getByText(/ejecutando/i)).toBeInTheDocument()
  })

  it('renders "Completado" for success status', () => {
    renderWithProviders(<StatusBadge status="success" />)
    expect(screen.getByText(/completado/i)).toBeInTheDocument()
  })

  it('renders "Error" for failed status', () => {
    renderWithProviders(<StatusBadge status="failed" />)
    expect(screen.getByText(/error/i)).toBeInTheDocument()
  })

  it('renders a span element', () => {
    renderWithProviders(<StatusBadge status="idle" />)
    expect(screen.getByText(/inactivo/i).tagName).toBe('SPAN')
  })
})
