import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import Footer from '../Footer'
import { renderWithProviders } from '../../test/helpers'

describe('Footer', () => {
  it('renders the church name', () => {
    renderWithProviders(<Footer />)
    expect(screen.getByText('Iglesia Bautista Libertad')).toBeInTheDocument()
  })

  it('renders the location', () => {
    renderWithProviders(<Footer />)
    expect(screen.getByText('Houston, TX')).toBeInTheDocument()
  })

  it('does NOT render any copyright text', () => {
    renderWithProviders(<Footer />)
    expect(screen.queryByText(/todos los derechos/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/all rights reserved/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/©/)).not.toBeInTheDocument()
  })

  it('renders the church logo image', () => {
    renderWithProviders(<Footer />)
    expect(screen.getByAltText('Church Logo')).toBeInTheDocument()
  })
})
