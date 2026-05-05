import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'
import { strings } from './translations'
import type { Lang, TranslationKey } from './translations'

interface LangCtx {
  lang:    Lang
  setLang: (l: Lang) => void
  t:       (key: TranslationKey) => string
}

const LangContext = createContext<LangCtx | null>(null)

const STORAGE_KEY = 'ibl-lang'

function savedLang(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'en' || v === 'es') return v
  } catch { /* ignore */ }
  return 'es'   // default to Spanish
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, _setLang] = useState<Lang>(savedLang)

  const setLang = (l: Lang) => {
    _setLang(l)
    try { localStorage.setItem(STORAGE_KEY, l) } catch { /* ignore */ }
  }

  const t = (key: TranslationKey) => strings[key][lang]

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LangContext)
  if (!ctx) throw new Error('useLanguage must be inside LanguageProvider')
  return ctx
}
