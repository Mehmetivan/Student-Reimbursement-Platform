'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { ArrowLeft, MessageSquare } from 'lucide-react'
import type { ReimbursementRequest, RequestStatus } from '@/types'

export default function StudentRequestDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [request, setRequest] = useState<ReimbursementRequest | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const all = await studentApi.getMyRequests()
        const found = all.find((r) => r.request_id === Number(params.id))
        setRequest(found ?? null)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [params.id])

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
    under_review: t('statusUnderReview'),
  }

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
              <RequestStatusBadge status={request.status} label={statusLabels[request.status]} />
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

        {/* Receipts */}
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900">Submitted Receipts</h3>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {request.receipts.map((receipt) => (
              <div key={receipt.receipt_id} className="bg-gray-50 rounded-xl p-3">
                <p className="text-xs text-gray-400 font-mono">{receipt.receipt_id}</p>
                <p className="text-xs text-gray-400 mt-1 font-mono truncate">{receipt.sha256_hash}</p>
              </div>
            ))}
          </CardBody>
        </Card>

      </div>
    </div>
  )
}
