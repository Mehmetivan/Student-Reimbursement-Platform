'use client'
// hooks/useAuth.ts
// Handles login, logout, current user state, and post-login redirects

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'
import { auth } from '@/lib/auth'
import type { MeResponse } from '@/types'

export function useAuth() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const currentUser = auth.getUser()

  const login = async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    try {
      const tokenData = await authApi.login(email, password)
      auth.saveToken(tokenData.access_token)

      // Fetch full user info and save it
      const user = await authApi.me()
      auth.saveUser(user)

      // Redirect based on role
      if (user.role === 'admin') {
        router.push('/admin/dashboard')
      } else {
        router.push('/dashboard')
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Login failed. Please check your credentials.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const register = async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.register(email, password)
      // After register, log them in automatically
      await login(email, password)
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Registration failed. Email may already be in use.'
      setError(message)
      setLoading(false)
    }
  }

  const logout = () => {
    auth.logout()
    router.push('/login')
  }

  return {
    currentUser,
    login,
    register,
    logout,
    loading,
    error,
  }
}
