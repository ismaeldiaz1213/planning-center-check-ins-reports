import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { setAuthToken } from '../api/client'

interface AuthContextValue {
  credential: string | null
  authRequired: boolean
  login: (credential: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  credential: null,
  authRequired: false,
  login: () => {},
  logout: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

interface Props {
  children: ReactNode
  authRequired: boolean
}

export function AuthProvider({ children, authRequired }: Props) {
  const [credential, setCredential] = useState<string | null>(null)

  const login = useCallback((cred: string) => {
    setCredential(cred)
    setAuthToken(cred)
  }, [])

  const logout = useCallback(() => {
    setCredential(null)
    setAuthToken(null)
  }, [])

  return (
    <AuthContext.Provider value={{ credential, authRequired, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
