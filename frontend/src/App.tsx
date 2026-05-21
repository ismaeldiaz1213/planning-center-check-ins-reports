import { useState } from 'react'
import { LanguageProvider } from './i18n/LanguageContext'
import Navbar from './components/Navbar'
import HomePage from './components/HomePage'
import Footer from './components/Footer'
import PreviewModal from './components/PreviewModal'
import JobModal from './components/JobModal'
import SettingsModal from './components/SettingsModal'
import LogsModal from './components/LogsModal'

export type ActiveModal = 'previews' | 'rutas' | 'escuela' | 'settings' | 'logs' | null

export default function App() {
  const [modal, setModal] = useState<ActiveModal>(null)

  return (
    <LanguageProvider>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--blue-bg)' }}>
        <Navbar />
        <div style={{ flex: 1 }}>
          <HomePage onOpen={setModal} />
        </div>
        <Footer />

        {modal === 'previews' && (
          <PreviewModal onClose={() => setModal(null)} />
        )}
        {(modal === 'rutas' || modal === 'escuela') && (
          <JobModal type={modal} onClose={() => setModal(null)} />
        )}
        {modal === 'settings' && (
          <SettingsModal onClose={() => setModal(null)} />
        )}
        {modal === 'logs' && (
          <LogsModal onClose={() => setModal(null)} />
        )}
      </div>
    </LanguageProvider>
  )
}
