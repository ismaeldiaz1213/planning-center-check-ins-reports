import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { LanguageProvider } from '../i18n/LanguageContext'
import type { Report } from '../types'

/** Render inside the LanguageProvider (default language: Spanish). */
export function renderWithProviders(ui: ReactElement) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}

/** A ReportSpec as /api/reports returns it, for component tests. */
export function makeReport(overrides: Partial<Report> = {}): Report {
  return {
    id:            'rutas',
    label:         'Rutas',
    icon:          '🚌',
    outputs:       ['address', 'simple'],
    show_route:    false,
    default_weeks: 5,
    default_theme: '',
    ...overrides,
  }
}

/** The three reports shipped in reports.yaml. */
export const RUTAS     = makeReport()
export const ESCUELA   = makeReport({ id: 'escuela', label: 'Escuela Dominical', icon: '📚', outputs: ['simple'], show_route: true })
export const ESCUELA_B = makeReport({ id: 'escuela-b', label: '"B" Escuela Dominical', icon: '📗', outputs: ['simple'], show_route: true })
export const ALL_REPORTS: Report[] = [RUTAS, ESCUELA, ESCUELA_B]
