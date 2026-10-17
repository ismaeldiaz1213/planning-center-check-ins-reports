import { useState, useEffect } from 'react'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { LanguageProvider } from './i18n/LanguageContext'
import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginOverlay from './components/LoginOverlay'
import Navbar from './components/Navbar'
import HomePage from './components/HomePage'
import Footer from './components/Footer'
import PreviewModal from './components/PreviewModal'
import JobModal from './components/JobModal'
import SettingsModal from './components/SettingsModal'
import LogsModal from './components/LogsModal'
import { useReports } from './hooks/useReports'

/** Fixed dashboard panels. Anything else is a report id from reports.yaml. */
export type FixedModal = 'previews' | 'settings' | 'logs'
export type ActiveModal = FixedModal | string | null

const FIXED_MODALS: readonly string[] = ['previews', 'settings', 'logs']

function AppShell() {
  const { credential, authRequired } = useAuth()
  const [modal, setModal] = useState<ActiveModal>(null)
  const { reports, loading: reportsLoading, error: reportsError } = useReports()

  if (authRequired && !credential) return <LoginOverlay />

  // A modal id that is not one of the fixed panels is a report id.
  const activeReport = modal && !FIXED_MODALS.includes(modal)
    ? reports.find(r => r.id === modal) ?? null
    : null

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--blue-bg)' }}>
      <Navbar />
      <div style={{ flex: 1 }}>
        <HomePage
          onOpen={setModal}
          reports={reports}
          reportsLoading={reportsLoading}
          reportsError={reportsError}
        />
      </div>
      <Footer />

      {modal === 'previews' && (
        <PreviewModal onClose={() => setModal(null)} />
      )}
      {activeReport && (
        <JobModal report={activeReport} onClose={() => setModal(null)} />
      )}
      {modal === 'settings' && (
        <SettingsModal onClose={() => setModal(null)} />
      )}
      {modal === 'logs' && (
        <LogsModal onClose={() => setModal(null)} />
      )}
    </div>
  )
}

export default function App() {
  const [clientId, setClientId] = useState<string>('')
  const [demoMode, setDemoMode] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    fetch('/api/auth/config')
      .then(r => r.json())
      .then(data => {
        setClientId(data.google_client_id ?? '')
        setDemoMode(data.demo_mode ?? false)
      })
      .catch(() => { setClientId(''); setDemoMode(false) })
      .finally(() => setAuthLoading(false))
  }, [])

  if (authLoading) return null

  return (
    <LanguageProvider>
      <AuthProvider authRequired={Boolean(clientId) && !demoMode} demoMode={demoMode}>
        <GoogleOAuthProvider clientId={clientId}>
          <AppShell />
        </GoogleOAuthProvider>
      </AuthProvider>
    </LanguageProvider>
  )
}
