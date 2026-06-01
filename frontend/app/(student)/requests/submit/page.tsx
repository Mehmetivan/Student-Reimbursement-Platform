'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Topbar } from '@/components/layout/Topbar'
import { Upload, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { cn, formatRiskScore, getRiskColor } from '@/lib/utils'

type SubmitResult = {
  action: string
  message: string
  receipt_id?: string
  request_id?: number
  final_assessment?: { total_risk_score: number; assessment: string }
  ocr_summary?: {
    stpt_id_found: boolean
    stpt_id_matches: boolean
    receipt_id_found: boolean
  }
}

export default function SubmitReceiptPage() {
  const { t } = useI18n()
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<SubmitResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFile = (f: File) => {
    setFile(f)
    setResult(null)
    setError(null)
  }

  const handleSubmit = async () => {
    if (!file) return
    setSubmitting(true)
    setError(null)
    try {
      const data = await studentApi.submitReceipt(file, comment || undefined)
      setResult(data as SubmitResult)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || t('error'))
    } finally {
      setSubmitting(false)
    }
  }

  const action = result?.action
  const isRejected = action === 'rejected'
  const isFlagged = action?.startsWith('flagged')
  const isApproved = action === 'approved'

  return (
    <div>
      <Topbar title={t('submitReceiptTitle')} />
      <div className="p-6 max-w-2xl flex flex-col gap-6">

        {/* Upload area */}
        {!result && (
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-900">{t('uploadReceipt')}</h2>
              <p className="text-xs text-gray-400 mt-0.5">JPG, PNG or PDF accepted. Max 10MB.</p>
            </CardHeader>
            <CardBody className="flex flex-col gap-4">
              <div
                onClick={() => document.getElementById('receipt-input')?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  const f = e.dataTransfer.files[0]
                  if (f) handleFile(f)
                }}
                className={cn(
                  'border-2 border-dashed rounded-2xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-colors',
                  dragOver ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-300 hover:bg-violet-50/30',
                  file && 'border-emerald-300 bg-emerald-50/30'
                )}
              >
                <Upload className={cn('h-8 w-8', file ? 'text-emerald-500' : 'text-gray-400')} />
                {file ? (
                  <div className="text-center">
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-sm font-medium text-gray-600">{t('clickToUpload')}</p>
                    <p className="text-xs text-gray-400 mt-0.5">or drag and drop</p>
                  </div>
                )}
              </div>
              <input
                id="receipt-input"
                type="file"
                accept=".jpg,.jpeg,.png,.pdf"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
              />

              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-gray-700">
                  Comment <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="e.g. March subscription receipt..."
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-900 bg-white resize-none focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent hover:border-gray-300"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600">
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <Button
                  variant="primary"
                  onClick={handleSubmit}
                  loading={submitting}
                  disabled={!file}
                  className="flex-1"
                >
                  {submitting ? t('submitting') : t('submitRequest')}
                </Button>
                <Button variant="secondary" onClick={() => router.push('/requests')}>
                  {t('cancel')}
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Result */}
        {result && (
          <Card>
            <CardBody className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                {isRejected && <XCircle className="h-6 w-6 text-red-500" />}
                {isFlagged && <AlertTriangle className="h-6 w-6 text-amber-500" />}
                {isApproved && <CheckCircle className="h-6 w-6 text-emerald-600" />}
                <div>
                  <p className="font-semibold text-gray-900">{result.message}</p>
                  {result.receipt_id && (
                    <p className="text-xs text-gray-400 mt-0.5">Receipt ID: {result.receipt_id}</p>
                  )}
                </div>
              </div>

              {/* OCR Summary */}
              {result.ocr_summary && (
                <div className="flex flex-col gap-2">
                  <p className="text-sm font-medium text-gray-700">OCR Results</p>
                  <div className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                      <span className="text-sm text-gray-600">STPT ID detected</span>
                      {result.ocr_summary.stpt_id_found
                        ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                        : <XCircle className="h-4 w-4 text-red-500" />}
                    </div>
                    <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                      <span className="text-sm text-gray-600">STPT ID matches your profile</span>
                      {result.ocr_summary.stpt_id_matches
                        ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                        : <XCircle className="h-4 w-4 text-red-500" />}
                    </div>
                    <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                      <span className="text-sm text-gray-600">Receipt transaction ID detected</span>
                      {result.ocr_summary.receipt_id_found
                        ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                        : <XCircle className="h-4 w-4 text-red-500" />}
                    </div>
                  </div>
                </div>
              )}

              {/* Risk summary */}
              {result.final_assessment && (
                <div className="bg-gray-50 rounded-xl p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-600">{t('riskScore')}</span>
                  <span className={cn('text-lg font-bold', getRiskColor(result.final_assessment.total_risk_score))}>
                    {formatRiskScore(result.final_assessment.total_risk_score)}
                  </span>
                </div>
              )}

              {/* Info box — not rejected */}
              {!isRejected && (
                <div className="bg-violet-50 border border-violet-100 rounded-xl px-4 py-3 text-sm text-violet-700">
                  Review your receipt on the next page. You can replace it or confirm it to send to admin.
                </div>
              )}

              <div className="flex gap-3">
                {!isRejected && result.request_id && (
                  <Button
                    variant="primary"
                    onClick={() => router.push(`/requests/${result.request_id}`)}
                    className="flex-1"
                  >
                    Review & Confirm
                  </Button>
                )}
                <Button
                  variant="secondary"
                  onClick={() => { setResult(null); setFile(null); setComment('') }}
                >
                  {isRejected ? 'Try Again' : 'Submit Another'}
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

      </div>
    </div>
  )
}
