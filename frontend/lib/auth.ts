'use client'
// lib/auth.ts
// Token and user storage helpers.
// Stores token in both localStorage (for API calls) and cookies (for middleware).
// Cookie max-age matches token expiry (8 hours) so both expire together.

import type { MeResponse } from '@/types'

const TOKEN_EXPIRY_SECONDS = 8 * 60 * 60 // 8 hours — must match ACCESS_TOKEN_EXPIRE_MINUTES in backend

function setCookie(name: string, value: string, maxAgeSeconds: number) {
  document.cookie = `${name}=${value};max-age=${maxAgeSeconds};path=/`
}

function deleteCookie(name: string) {
  document.cookie = `${name}=;max-age=0;path=/`
}

export const auth = {
  saveToken: (token: string) => {
    localStorage.setItem('token', token)
    setCookie('token', token, TOKEN_EXPIRY_SECONDS)
  },

  getToken: (): string | null => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('token')
  },

  saveUser: (user: MeResponse) => {
    localStorage.setItem('user', JSON.stringify(user))
    setCookie('role', user.role, TOKEN_EXPIRY_SECONDS)
  },

  getUser: (): MeResponse | null => {
    if (typeof window === 'undefined') return null
    const raw = localStorage.getItem('user')
    if (!raw) return null
    try {
      return JSON.parse(raw)
    } catch {
      return null
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    deleteCookie('token')
    deleteCookie('role')
  },

  isLoggedIn: (): boolean => {
    return !!auth.getToken()
  },

  isAdmin: (): boolean => {
    return auth.getUser()?.role === 'admin'
  },

  isStudent: (): boolean => {
    return auth.getUser()?.role === 'student'
  },
}