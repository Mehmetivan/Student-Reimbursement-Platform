'use client'
// lib/auth.ts
// Token and user storage helpers.
// Stores token in both localStorage (for API calls) and cookies (for middleware).

import type { MeResponse } from '@/types'

function setCookie(name: string, value: string, days = 7) {
  const expires = new Date()
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000)
  document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`
}

function deleteCookie(name: string) {
  document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/`
}

export const auth = {
  saveToken: (token: string) => {
    localStorage.setItem('token', token)
    setCookie('token', token)
  },

  getToken: (): string | null => {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('token')
  },

  saveUser: (user: MeResponse) => {
    localStorage.setItem('user', JSON.stringify(user))
    setCookie('role', user.role)
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
