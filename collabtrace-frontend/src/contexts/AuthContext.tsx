import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { authApi } from '../api/auth'
import { TOKEN_KEY } from '../api/client'
import type { LoginResponse, User } from '../types'

interface AuthState {
  user: User | null
  loading: boolean
  completeLogin: (response: LoginResponse) => void
  refreshUser: () => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(sessionStorage.getItem(TOKEN_KEY)))

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    if (!sessionStorage.getItem(TOKEN_KEY)) { setLoading(false); return }
    try { setUser(await authApi.me()) }
    catch { logout() }
    finally { setLoading(false) }
  }, [logout])

  useEffect(() => { void refreshUser() }, [refreshUser])
  useEffect(() => {
    const unauthorized = () => logout()
    window.addEventListener('collabtrace:unauthorized', unauthorized)
    return () => window.removeEventListener('collabtrace:unauthorized', unauthorized)
  }, [logout])

  const completeLogin = useCallback((response: LoginResponse) => {
    sessionStorage.setItem(TOKEN_KEY, response.access_token)
    setUser(response.user)
  }, [])

  const value = useMemo(() => ({ user, loading, completeLogin, refreshUser, logout }), [user, loading, completeLogin, refreshUser, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
