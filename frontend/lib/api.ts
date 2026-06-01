// lib/api.ts
// All API calls to the FastAPI backend in one place.
// Every page/hook imports from here — never writes fetch() directly.

import axios from 'axios'
import type {
  LoginResponse,
  RegisterResponse,
  MeResponse,
  StudentProfile,
  StudentDetail,
  ReimbursementRequest,
} from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Axios instance — attaches JWT token to every request automatically
export const api = axios.create({
  baseURL: BASE_URL,
})

// Interceptor: read token from localStorage and add to Authorization header
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// Interceptor: if backend returns 401, clear token and redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: async (email: string, password: string): Promise<RegisterResponse> => {
    const { data } = await api.post('/auth/register', { email, password })
    return data
  },

  login: async (email: string, password: string): Promise<LoginResponse> => {
    const formData = new URLSearchParams()
    formData.append('username', email)
    formData.append('password', password)
    const { data } = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return data
  },

  me: async (): Promise<MeResponse> => {
    const { data } = await api.get('/auth/me')
    return data
  },
}

// ── Student ───────────────────────────────────────────────────────────────────

export const studentApi = {
  getProfile: async (): Promise<StudentProfile> => {
    const { data } = await api.get('/students/me')
    return data
  },

  updateProfile: async (payload: { name?: string; iban?: string }): Promise<StudentProfile> => {
    const { data } = await api.patch('/students/me', payload)
    return data
  },

  uploadStudentId: async (file: File): Promise<unknown> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/students/me/documents/student-id', formData)
    return data
  },

  uploadStptCard: async (file: File): Promise<unknown> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/students/me/documents/stpt-card', formData)
    return data
  },

  uploadBankProof: async (file: File): Promise<unknown> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/students/me/documents/bank-proof', formData)
    return data
  },

  getMyRequests: async (status?: string): Promise<ReimbursementRequest[]> => {
    const params = status ? { status } : {}
    const { data } = await api.get('/students/me/requests', { params })
    return data
  },

  submitReceipt: async (file: File, comment?: string): Promise<unknown> => {
    const formData = new FormData()
    formData.append('file', file)
    if (comment) formData.append('comment', comment)
    const { data } = await api.post('/receipts/submit', formData)
    return data
  },

  resubmitReceipt: async (requestId: number, file: File, comment?: string): Promise<unknown> => {
    const formData = new FormData()
    formData.append('file', file)
    if (comment) formData.append('comment', comment)
    const { data } = await api.patch(`/receipts/resubmit/${requestId}`, formData)
    return data
  },

  getMyDocuments: async (): Promise<{ document_id: string; document_type: string; file_path: string; uploaded_at: string }[]> => {
    const { data } = await api.get('/students/me/documents')
    return data
  },
  confirmReceipt: async (requestId: number): Promise<unknown> => {
    const { data } = await api.patch(`/receipts/confirm/${requestId}`)
    return data
  },
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export const adminApi = {
  getStudents: async (status?: string): Promise<StudentDetail[]> => {
    const params = status ? { status } : {}
    const { data } = await api.get('/admin/students', { params })
    return data
  },

  getStudent: async (studentId: number): Promise<StudentDetail> => {
    const { data } = await api.get(`/admin/students/${studentId}`)
    return data
  },

  decideStudentAccount: async (
    studentId: number,
    decision: 'approve' | 'reject',
    note?: string
  ): Promise<unknown> => {
    const { data } = await api.patch(`/admin/students/${studentId}/decision`, { decision, note })
    return data
  },

  editStudent: async (
    studentId: number,
    payload: { name?: string; iban?: string; stpt_id?: string }
  ): Promise<unknown> => {
    const { data } = await api.patch(`/admin/students/${studentId}/edit`, payload)
    return data
  },

  getRequests: async (status?: string, timeframe?: string): Promise<ReimbursementRequest[]> => {
    const params: Record<string, string> = {}
    if (status) params.status = status
    if (timeframe) params.timeframe = timeframe
    const { data } = await api.get('/admin/requests', { params })
    return data
  },

  decideRequest: async (
    requestId: number,
    decision: 'approve' | 'reject',
    note?: string
  ): Promise<ReimbursementRequest> => {
    const { data } = await api.patch(`/admin/requests/${requestId}/decision`, { decision, note })
    return data
  },


}
