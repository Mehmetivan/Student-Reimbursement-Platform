'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { adminApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { FraudLayerResults } from '@/components/features/FraudLayerResults'
import { ArrowLeft, CheckCircle, XCircle, Eye } from 'lucide-react'
import type { ReimbursementRequest, RequestStatus } from '@/types'

export default function AdminRequestDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [request, setRequest] = useState<ReimbursementRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | 'under_review' | null>(null)
  const [note, setNote] = useState('')
  const [acting, setActing] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const all = await adminApi.getRequests()
        const found = all.find((r) => r.request_id === Number(params.id))
        setRequest(found ?? null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [params.id])

  const handleDecision = async () => {
    if (!decisionModal || !request) return
    setActing(true)
    try {
      const updated = await adminApi.decideRequest(request.request_id, decisionModal, note)
      setRequest(updated)
      setDecisionModal(null)
      setNote('')
    } finally {
      setActing(false)
    }
  }

  if (loading) return <PageSpinner />
  if (!request) return <div className="p-6 text-gray-500">Request not found</div>

  const statusLabels: Record<RequestStatus, string> = {
    pending: t('statusPending'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
    under_review: t('statusUnderReview'),
  }

  const canDecide = request.status === 'pending' || request.status === 'under_review'

  return (
    <div>
      <Topbar title={`Request #${request.request_id}`} />
      <div className="p-6 max-w-2xl flex flex-col gap-4">

        <Button variant="ghost" size="sm" onClick={() => router.push('/admin/requests')} className="self-start">
          <ArrowLeft className="h-4 w-4" /> {t('requests')}
        </Button>

        {/* Status overview */}
        <Card>
          <CardBody className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">{t('status')}</p>
              <RequestStatusBadge status={request.status} label={statusLabels[request.status]} />
            </div>
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">Student ID</p>
              <p className="text-sm font-medium text-gray-900">{request.student_id}</p>
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
            {request.admin_feedback && (
              <div className="bg-gray-50 rounded-xl p-3 mt-1">
                <p className="text-xs text-gray-400 mb-1">{t('adminFeedback')}</p>
                <p className="text-sm text-gray-700">{request.admin_feedback}</p>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Decision buttons */}
        {canDecide && (
          <div className="flex gap-2 flex-wrap">
            <Button variant="primary" onClick={() => setDecisionModal('approve')} className="flex-1">
              <CheckCircle className="h-4 w-4" /> {t('approveRequest')}
            </Button>
            <Button variant="danger" onClick={() => setDecisionModal('reject')} className="flex-1">
              <XCircle className="h-4 w-4" /> {t('rejectRequest')}
            </Button>
            <Button variant="secondary" onClick={() => setDecisionModal('under_review')}>
              <Eye className="h-4 w-4" /> {t('markUnderReview')}
            </Button>
          </div>
        )}

        {/* Fraud analysis per receipt */}
        {request.receipts.map((receipt) => (
          <div key={receipt.receipt_id}>
            {receipt.risk_assessment ? (
              <FraudLayerResults assessment={receipt.risk_assessment} />
            ) : (
              <Card>
                <CardBody>
                  <p className="text-sm text-gray-400">No fraud analysis available for this receipt.</p>
                </CardBody>
              </Card>
            )}
          </div>
        ))}

      </div>

      {/* Decision modal */}
      <Modal
        open={!!decisionModal}
        onClose={() => { setDecisionModal(null); setNote('') }}
        title={
          decisionModal === 'approve' ? t('approveRequest') :
          decisionModal === 'reject' ? t('rejectRequest') :
          t('markUnderReview')
        }
      >
        <div className="flex flex-col gap-4">
          <Input
            label={t('feedbackLabel')}
            placeholder="Optional message to the student..."
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex gap-3">
            <Button
              variant={decisionModal === 'approve' ? 'primary' : decisionModal === 'reject' ? 'danger' : 'secondary'}
              onClick={handleDecision}
              loading={acting}
              className="flex-1"
            >
              {t('confirm')}
            </Button>
            <Button variant="secondary" onClick={() => setDecisionModal(null)} className="flex-1">
              {t('cancel')}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
