// lib/utils.ts
// Formatting helpers used across the app

import { clsx, type ClassValue } from 'clsx'
import type { AccountStatus, RequestStatus } from '@/types'

// Tailwind class merging helper
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

// Format ISO date string to readable format
export function formatDate(dateString: string | null, lang: 'en' | 'ro' = 'en'): string {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  return date.toLocaleDateString(lang === 'ro' ? 'ro-RO' : 'en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Format risk score 0-1 to percentage with color class
export function getRiskColor(score: number): string {
  if (score >= 0.7) return 'text-red-600'
  if (score >= 0.4) return 'text-amber-500'
  return 'text-emerald-600'
}

export function getRiskBgColor(score: number): string {
  if (score >= 0.7) return 'bg-red-50 border-red-200'
  if (score >= 0.4) return 'bg-amber-50 border-amber-200'
  return 'bg-emerald-50 border-emerald-200'
}

export function formatRiskScore(score: number): string {
  return `${Math.round(score * 100)}%`
}

// Account status → badge color
export function getAccountStatusColor(status: AccountStatus): string {
  switch (status) {
    case 'approved': return 'bg-emerald-100 text-emerald-700'
    case 'pending_approval': return 'bg-amber-100 text-amber-700'
    case 'rejected': return 'bg-red-100 text-red-700'
    case 'incomplete': return 'bg-gray-100 text-gray-600'
    default: return 'bg-gray-100 text-gray-600'
  }
}

// Request status → badge color
export function getRequestStatusColor(status: RequestStatus): string {
  switch (status) {
    case 'approved': return 'bg-emerald-100 text-emerald-700'
    case 'pending': return 'bg-amber-100 text-amber-700'
    case 'rejected': return 'bg-red-100 text-red-700'
    case 'under_review': return 'bg-blue-100 text-blue-700'
    default: return 'bg-gray-100 text-gray-600'
  }
}

// Check if profile is complete enough to submit requests
export function isProfileComplete(profile: {
  name: string | null
  iban: string | null
  stpt_id: string | null
  documents_uploaded: {
    student_id_photo: boolean
    stpt_card: boolean
    bank_proof: boolean
  }
}): boolean {
  return !!(
    profile.name &&
    profile.iban &&
    profile.stpt_id &&
    profile.documents_uploaded.student_id_photo &&
    profile.documents_uploaded.stpt_card &&
    profile.documents_uploaded.bank_proof
  )
}
