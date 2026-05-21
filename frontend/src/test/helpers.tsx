import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { LanguageProvider } from '../i18n/LanguageContext'

/** Render inside the LanguageProvider (default language: Spanish). */
export function renderWithProviders(ui: ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}

/** Shallow mock of a resolved fetch response. */
export function mockFetchOnce(data: unknown) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => data,
  } as any)
}

/** Stub fetch to reject once. */
export function mockFetchError(message = 'Network error') {
  global.fetch = vi.fn().mockRejectedValueOnce(new Error(message))
}
