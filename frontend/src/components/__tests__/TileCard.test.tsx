import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TileCard from '../TileCard'
import { renderWithProviders } from '../../test/helpers'

describe('TileCard', () => {
  const baseProps = {
    icon: '📄',
    title: 'PDF Previews',
    description: 'Generate and view roster PDFs.',
  }

  describe('active tile', () => {
    it('renders the icon, title and description', () => {
      renderWithProviders(<TileCard {...baseProps} active onClick={vi.fn()} />)
      expect(screen.getByText('📄')).toBeInTheDocument()
      expect(screen.getByText('PDF Previews')).toBeInTheDocument()
      expect(screen.getByText('Generate and view roster PDFs.')).toBeInTheDocument()
    })

    it('renders the "Abrir →" CTA in Spanish', () => {
      renderWithProviders(<TileCard {...baseProps} active onClick={vi.fn()} />)
      expect(screen.getByText('Abrir →')).toBeInTheDocument()
    })

    it('calls onClick when the card is clicked', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()
      renderWithProviders(<TileCard {...baseProps} active onClick={handleClick} />)
      await user.click(screen.getByRole('button'))
      expect(handleClick).toHaveBeenCalledOnce()
    })

    it('calls onClick when Enter is pressed on the card', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()
      renderWithProviders(<TileCard {...baseProps} active onClick={handleClick} />)
      screen.getByRole('button').focus()
      await user.keyboard('{Enter}')
      expect(handleClick).toHaveBeenCalledOnce()
    })
  })

  describe('inactive tile', () => {
    it('renders "Próximamente" instead of CTA', () => {
      renderWithProviders(<TileCard {...baseProps} active={false} />)
      expect(screen.getByText('Próximamente')).toBeInTheDocument()
      expect(screen.queryByText('Abrir →')).not.toBeInTheDocument()
    })

    it('has no button role on inactive tile', () => {
      renderWithProviders(<TileCard {...baseProps} active={false} />)
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })
})
