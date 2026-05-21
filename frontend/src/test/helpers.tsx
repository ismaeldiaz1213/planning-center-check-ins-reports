import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { LanguageProvider } from '../i18n/LanguageContext'

/** Render inside the LanguageProvider (default language: Spanish). */
export function renderWithProviders(ui: ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}
