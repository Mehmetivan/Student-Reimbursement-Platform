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

export default function SubmitReceiptPage() {
  const { t } = useI18n()
  const router = useRouter()
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
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
      const data = await studentApi.submitReceipt(file)
      setResult(data as Record<string, unknown>)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || t('error'))
    } finally {
      setSubmitting(false)
    }
  }

  const action = result?.action as string | undefined
  const isApproved = action === 'approved'
  const isRejected = action === 'rejected'
  const isFlagged = action?.startsWith('flagged')

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
                {isApproved && <CheckCircle className="h-6 w-6 text-emerald-600" />}
                {isRejected && <XCircle className="h-6 w-6 text-red-500" />}
                {isFlagged && <AlertTriangle className="h-6 w-6 text-amber-500" />}
                <div>
                  <p className="font-semibold text-gray-900">{result.message as string}</p>
                  {result.receipt_id && (
                    <p className="text-xs text-gray-400 mt-0.5">Receipt ID: {result.receipt_id as string}</p>
                  )}
                </div>
              </div>

              {/* Risk summary */}
              {result.final_assessment && (
                <div className="bg-gray-50 rounded-xl p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-600">{t('riskScore')}</span>
                  <span className={cn('text-lg font-bold', getRiskColor(
                    (result.final_assessment as Record<string, unknown>).total_risk_score as number
                  ))}>
                    {formatRiskScore(
                      (result.final_assessment as Record<string, unknown>).total_risk_score as number
                    )}
                  </span>
                </div>
              )}

              <div className="flex gap-3">
                <Button
                  variant="primary"
                  onClick={() => router.push('/requests')}
                  className="flex-1"
                >
                  {t('myRequests')}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => { setResult(null); setFile(null) }}
                >
                  Submit Another
                </Button>
              </div>
            </CardBody>
          </Card>
        )}

      </div>
    </div>
  )
}
