'use client'
import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { formatDate, formatRiskScore, getRiskColor } from '@/lib/utils'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { ArrowLeft, MessageSquare, Image, ExternalLink, Upload, CheckCircle, XCircle, RefreshCw, Send } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReimbursementRequest, RequestStatus } from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type OcrResult = {
  ocr_summary?: {
    stpt_id_found: boolean
    stpt_id_matches: boolean
    receipt_id_found: boolean
  }
  final_assessment?: {
    total_risk_score: number
    assessment: string
  }
  message?: string
}

export default function StudentRequestDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [request, setRequest] = useState<ReimbursementRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingReceipt, setViewingReceipt] = useState<string | null>(null)
  const [resubmitFile, setResubmitFile] = useState<File | null>(null)
  const [resubmitComment, setResubmitComment] = useState('')
  const [resubmitting, setResubmitting] = useState(false)
  const [resubmitError, setResubmitError] = useState<string | null>(null)
  const [resubmitResult, setResubmitResult] = useState<OcrResult | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)

  const loadRequest = useCallback(async () => {
    try {
      const all = await studentApi.getMyRequests()
      const found = all.find((r) => r.request_id === Number(params.id))
      setRequest(found ?? null)
    } finally {
      setLoading(false)
    }
  }, [params.id])

  useEffect(() => { loadRequest() }, [loadRequest])

  const handleResubmit = async () => {
    if (!resubmitFile || !request) return
    setResubmitting(true)
    setResubmitError(null)
    setResubmitResult(null)
    try {
      const data = await studentApi.resubmitReceipt(request.request_id, resubmitFile, resubmitComment || undefined)
      setResubmitResult(data as OcrResult)
      setResubmitFile(null)
      setResubmitComment('')
      await loadRequest()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setResubmitError(msg || 'Resubmission failed')
    } finally {
      setResubmitting(false)
    }
  }

  const handleConfirm = async () => {
    if (!request) return
    setConfirming(true)
    setConfirmError(null)
    try {
      await studentApi.confirmReceipt(request.request_id)
      router.push('/requests')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setConfirmError(msg || 'Confirmation failed')
      setConfirming(false)
    }
  }

  if (loading) return <PageSpinner />
  if (!request) return (
    <div className="p-6">
      <p className="text-gray-500">Request not found.</p>
      <Button variant="ghost" onClick={() => router.push('/requests')} className="mt-4">
        <ArrowLeft className="h-4 w-4" /> {t('backToRequests')}
      </Button>
    </div>
  )

  const statusLabels: Record<RequestStatus, string> = {
    pending: t('statusPending'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const isUnconfirmed = !request.confirmed && request.status === 'pending'

  return (
    <div>
      <Topbar title={`Request #${request.request_id}`} />
      <div className="p-6 max-w-2xl flex flex-col gap-4">

        <Button variant="ghost" size="sm" onClick={() => router.push('/requests')} className="self-start">
          <ArrowLeft className="h-4 w-4" />
          {t('backToRequests')}
        </Button>

        {/* Status card */}
        <Card>
          <CardBody className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{t('status')}</p>
              <div className="flex items-center gap-2">
                {isUnconfirmed && (
                  <span className="text-xs font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2 py-1 rounded-lg">
                    Not yet submitted to admin
                  </span>
                )}
                <RequestStatusBadge status={request.status} label={statusLabels[request.status]} />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{t('submittedOn')}</p>
              <p className="text-sm font-medium text-gray-900">{formatDate(request.submit_timestamp)}</p>
            </div>
            {request.review_timestamp && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">{t('reviewedOn')}</p>
                <p className="text-sm font-medium text-gray-900">{formatDate(request.review_timestamp)}</p>
              </div>
            )}
            {request.resubmission_count > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500">Resubmissions</p>
                <p className="text-sm font-medium text-gray-900">{request.resubmission_count}</p>
              </div>
            )}
            {request.comment && (
              <div className="bg-gray-50 rounded-xl p-3 mt-1">
                <p className="text-xs text-gray-400 mb-1">Your comment</p>
                <p className="text-sm text-gray-700">{request.comment}</p>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Admin feedback */}
        {request.admin_feedback && (
          <Card>
            <CardBody className="flex items-start gap-3">
              <MessageSquare className="h-5 w-5 text-violet-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-gray-800 mb-1">{t('adminFeedback')}</p>
                <p className="text-sm text-gray-600">{request.admin_feedback}</p>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Receipt */}
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Submitted Receipt</h3>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {request.receipts.map((receipt) => (
              <div key={receipt.receipt_id} className="flex flex-col gap-2">
                {receipt.file_path ? (
                  <>
                    <img
                      src={`${BASE_URL}/${receipt.file_path}`}
                      alt="Receipt"
                      className="w-full rounded-xl border border-gray-100 object-contain max-h-64 cursor-pointer hover:opacity-90 transition-opacity"
                      onClick={() => setViewingReceipt(`${BASE_URL}/${receipt.file_path}`)}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      className="self-start"
                      onClick={() => setViewingReceipt(`${BASE_URL}/${receipt.file_path!}`)}
                    >
                      <Image className="h-4 w-4" />
                      View Receipt
                    </Button>
                  </>
                ) : (
                  <div className="bg-gray-50 rounded-xl p-3">
                    <p className="text-xs text-gray-400 font-mono">{receipt.receipt_id}</p>
                  </div>
                )}
              </div>
            ))}
          </CardBody>
        </Card>

        {/* Resubmit OCR results */}
        {resubmitResult && (
          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900">New Receipt Results</h3>
              <p className="text-xs text-gray-400 mt-0.5">Results from your replaced receipt</p>
            </CardHeader>
            <CardBody className="flex flex-col gap-3">
              {resubmitResult.ocr_summary && (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                    <span className="text-sm text-gray-600">STPT ID detected</span>
                    {resubmitResult.ocr_summary.stpt_id_found
                      ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                      : <XCircle className="h-4 w-4 text-red-500" />}
                  </div>
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                    <span className="text-sm text-gray-600">STPT ID matches your profile</span>
                    {resubmitResult.ocr_summary.stpt_id_matches
                      ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                      : <XCircle className="h-4 w-4 text-red-500" />}
                  </div>
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-2.5">
                    <span className="text-sm text-gray-600">Receipt transaction ID detected</span>
                    {resubmitResult.ocr_summary.receipt_id_found
                      ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                      : <XCircle className="h-4 w-4 text-red-500" />}
                  </div>
                </div>
              )}
              {resubmitResult.final_assessment && (
                <div className="bg-gray-50 rounded-xl p-4 flex items-center justify-between">
                  <span className="text-sm text-gray-600">{t('riskScore')}</span>
                  <span className={cn('text-lg font-bold', getRiskColor(resubmitResult.final_assessment.total_risk_score))}>
                    {formatRiskScore(resubmitResult.final_assessment.total_risk_score)}
                  </span>
                </div>
              )}
            </CardBody>
          </Card>
        )}

        {/* Confirm or Replace — only shown when not yet confirmed */}
        {isUnconfirmed && (
          <>
            <Card>
              <CardBody className="flex flex-col gap-3">
                <p className="text-sm text-gray-600">
                  Review your receipt above. When you are happy with it, confirm your submission to send it to admin for review.
                </p>
                {confirmError && (
                  <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600 flex items-center gap-2">
                    <XCircle className="h-4 w-4" />
                    {confirmError}
                  </div>
                )}
                <Button variant="primary" onClick={handleConfirm} loading={confirming} className="w-full">
                  <Send className="h-4 w-4" />
                  Confirm & Submit to Admin
                </Button>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 text-violet-600" />
                  Replace Receipt
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Uploaded the wrong receipt or OCR failed? Replace it before confirming.
                </p>
              </CardHeader>
              <CardBody className="flex flex-col gap-3">
                <div
                  onClick={() => document.getElementById('resubmit-input')?.click()}
                  className={cn(
                    'border-2 border-dashed rounded-xl p-6 flex flex-col items-center gap-2 cursor-pointer transition-colors',
                    resubmitFile
                      ? 'border-emerald-300 bg-emerald-50/30'
                      : 'border-gray-200 hover:border-violet-300 hover:bg-violet-50/30'
                  )}
                >
                  <Upload className={cn('h-6 w-6', resubmitFile ? 'text-emerald-500' : 'text-gray-400')} />
                  {resubmitFile ? (
                    <p className="text-sm font-medium text-gray-900">{resubmitFile.name}</p>
                  ) : (
                    <p className="text-sm text-gray-500">Click to select new receipt</p>
                  )}
                </div>
                <input
                  id="resubmit-input"
                  type="file"
                  accept=".jpg,.jpeg,.png,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) { setResubmitFile(f); setResubmitResult(null) }
                  }}
                />

                <textarea
                  value={resubmitComment}
                  onChange={(e) => setResubmitComment(e.target.value)}
                  placeholder="Optional comment about this replacement..."
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm text-gray-900 bg-white resize-none focus:outline-none focus:ring-2 focus:ring-violet-500 hover:border-gray-300"
                />

                {resubmitError && (
                  <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600 flex items-center gap-2">
                    <XCircle className="h-4 w-4" />
                    {resubmitError}
                  </div>
                )}

                <Button
                  variant="secondary"
                  onClick={handleResubmit}
                  loading={resubmitting}
                  disabled={!resubmitFile}
                >
                  <RefreshCw className="h-4 w-4" />
                  Replace Receipt
                </Button>
              </CardBody>
            </Card>
          </>
        )}

      </div>

      <Modal open={!!viewingReceipt} onClose={() => setViewingReceipt(null)} title="Receipt">
        {viewingReceipt && (
          <div className="flex flex-col gap-3">
            <img src={viewingReceipt} alt="Receipt" className="w-full rounded-xl object-contain max-h-[70vh]" />
            <a href={viewingReceipt} target="_blank" rel="noopener noreferrer"
              className="text-sm text-violet-600 hover:underline flex items-center gap-1 self-center">
              <ExternalLink className="h-3.5 w-3.5" /> Open in new tab
            </a>
          </div>
        )}
      </Modal>
    </div>
  )
}
