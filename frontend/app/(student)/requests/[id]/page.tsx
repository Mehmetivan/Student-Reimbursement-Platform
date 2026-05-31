'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { ArrowLeft, MessageSquare, Image, ExternalLink } from 'lucide-react'
import type { ReimbursementRequest, RequestStatus } from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function StudentRequestDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [request, setRequest] = useState<ReimbursementRequest | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingReceipt, setViewingReceipt] = useState<string | null>(null)

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
                    <p className="text-xs text-gray-400 mt-1 font-mono truncate">{receipt.sha256_hash}</p>
                  </div>
                )}
              </div>
            ))}
          </CardBody>
        </Card>

      </div>

      {/* Receipt viewer modal */}
      <Modal
        open={!!viewingReceipt}
        onClose={() => setViewingReceipt(null)}
        title="Receipt"
      >
        {viewingReceipt && (
          <div className="flex flex-col gap-3">
            <img
              src={viewingReceipt}
              alt="Receipt"
              className="w-full rounded-xl object-contain max-h-[70vh]"
            />
            <a
              href={viewingReceipt}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-violet-600 hover:underline flex items-center gap-1 self-center"
            >
              <ExternalLink className="h-3.5 w-3.5" /> Open in new tab
            </a>
          </div>
        )}
      </Modal>
    </div>
  )
}
