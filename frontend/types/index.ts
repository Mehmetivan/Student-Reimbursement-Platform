// types/index.ts
// All TypeScript interfaces matching the FastAPI backend response shapes

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string
  token_type: string
  role: 'student' | 'admin'
}

export interface RegisterResponse {
  account_id: number
  student_id: number
  email: string
  role: string
  account_status: AccountStatus
}

export interface MeResponse {
  account_id: number
  email: string
  role: 'student' | 'admin'
  student_id?: number
  account_status?: AccountStatus
}

// ── Student ───────────────────────────────────────────────────────────────────

export type AccountStatus =
  | 'incomplete'
  | 'pending_approval'
  | 'approved'
  | 'rejected'

export interface DocumentsUploaded {
  student_id_photo: boolean
  stpt_card: boolean
  bank_proof: boolean
}

export interface StudentProfile {
  student_id: number
  name: string | null
  email: string
  iban: string | null
  stpt_id: string | null
  account_status: AccountStatus
  documents_uploaded: DocumentsUploaded
}

export interface StudentDocument {
  document_id: string
  document_type: 'STUDENT_ID' | 'STPT_CARD' | 'BANK_PROOF'
  file_path: string
  uploaded_at: string
}

export interface StudentDetail {
  student_id: number
  name: string | null
  email: string
  iban: string | null
  stpt_id: string | null
  account_status: AccountStatus
  documents: StudentDocument[]
}

// ── Requests ──────────────────────────────────────────────────────────────────

export type RequestStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'under_review'

export interface RiskAssessment {
  total_risk_score: number
  assessment: 'low_risk' | 'medium_risk' | 'high_risk'
  layer1_risk: number
  layer2_risk: number
  layer3_risk: number
  layer4_risk: number
  risk_factors: {
    layer1_hash: {
      fraud_detected: boolean
      duplicate_detected: boolean
      risk: number
    }
    layer2_exif: {
      has_editing_software: boolean
      editing_software: string | null
      flags: string[]
      risk: number
    }
    layer3_ocr: {
      stpt_id_matches: boolean | null
      extracted_stpt_id: string | null
      expected_stpt_id: string | null
      flags: string[]
      risk: number
    }
    layer4_anomaly: {
      risk: number
    }
  }
}

export interface Receipt {
  receipt_id: string
  file_path: string
  sha256_hash: string
  risk_assessment?: RiskAssessment
}

export interface ReimbursementRequest {
  request_id: number
  student_id: number
  status: RequestStatus
  comment: string | null
  admin_feedback: string | null
  submit_timestamp: string
  review_timestamp: string | null
  receipts: Receipt[]
}

// ── API Error ─────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string
}
