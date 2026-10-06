import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export interface AuthUser {
  username: string
  name: string
  avatar_url: string
}

export interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  authEnabled: boolean
  isLoading: boolean
  login: () => void
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authEnabled, setAuthEnabled] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const fetchAuthStatus = async () => {
    try {
      const res = await fetch('/api/auth/me')
      if (res.ok) {
        const data = await res.json()
        setAuthEnabled(Boolean(data.auth_enabled))
        if (data.authenticated) {
          setIsAuthenticated(true)
          setUser({
            username: data.username || '',
            name: data.name || data.username || '',
            avatar_url: data.avatar_url || ''
          })
        } else {
          setIsAuthenticated(!data.auth_enabled)
          setUser(null)
        }
      } else {
        setIsAuthenticated(false)
        setUser(null)
      }
    } catch {
      setIsAuthenticated(false)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAuthStatus()
  }, [])

  const login = () => {
    window.location.href = '/api/auth/github/login'
  }

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' })
    } finally {
      setIsAuthenticated(false)
      setUser(null)
      window.location.href = '/'
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        authEnabled,
        isLoading,
        login,
        logout,
        refreshAuth: fetchAuthStatus
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
