import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LoginOverlay from '../LoginOverlay'
import { renderWithProviders } from '../../test/helpers'

const mockLogin = vi.fn()

vi.mock('@react-oauth/google', () => ({
  GoogleLogin: ({ onSuccess }: { onSuccess: (r: { credential: string }) => void }) => (
    <button onClick={() => onSuccess({ credential: 'mock-token' })}>Sign in with Google</button>
  ),
}))

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({ login: mockLogin, logout: vi.fn(), credential: null, authRequired: true }),
}))

describe('LoginOverlay', () => {
  it('renders the title', () => {
    renderWithProviders(<LoginOverlay />)
    expect(screen.getByText('Church Roster')).toBeInTheDocument()
  })

  it('renders the subtitle', () => {
    renderWithProviders(<LoginOverlay />)
    expect(screen.getByText(/inicia sesión para continuar/i)).toBeInTheDocument()
  })

  it('renders the domain restriction hint', () => {
    renderWithProviders(<LoginOverlay />)
    expect(screen.getByText(/autorizadas/i)).toBeInTheDocument()
  })

  it('renders the Google sign-in button', () => {
    renderWithProviders(<LoginOverlay />)
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
  })

  it('calls login with the credential on successful sign-in', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LoginOverlay />)
    await user.click(screen.getByRole('button', { name: /sign in with google/i }))
    expect(mockLogin).toHaveBeenCalledWith('mock-token')
  })
})
