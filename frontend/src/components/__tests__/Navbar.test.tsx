import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Navbar from '../Navbar'
import { renderWithProviders } from '../../test/helpers'

describe('Navbar', () => {
  beforeEach(() => {
    // Reset language to Spanish default before each test
    localStorage.clear()
  })
  it('renders the site title', () => {
    renderWithProviders(<Navbar />)
    expect(screen.getByText('Roster Administrador')).toBeInTheDocument()
  })

  it('renders language toggle buttons', () => {
    renderWithProviders(<Navbar />)
    expect(screen.getByRole('button', { name: 'ES' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'EN' })).toBeInTheDocument()
  })

  it('defaults to Spanish (ES button aria-pressed=true)', () => {
    renderWithProviders(<Navbar />)
    expect(screen.getByRole('button', { name: 'ES' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('switches to English when EN is clicked', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Navbar />)
    await user.click(screen.getByRole('button', { name: 'EN' }))
    expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'ES' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders the dashboard navigation link with Spanish text', () => {
    renderWithProviders(<Navbar />)
    expect(screen.getByRole('link', { name: 'Inicio' })).toBeInTheDocument()
  })
})
