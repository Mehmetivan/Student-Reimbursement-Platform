'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { PlusCircle, FileText, ChevronRight } from 'lucide-react'
import type { ReimbursementRequest, RequestStatus } from '@/types'

const STATUS_FILTERS: { value: string; labelKey: 'allStatuses' | 'statusPending' | 'statusApproved' | 'statusRejected' | 'statusUnderReview' }[] = [
  { value: '', labelKey: 'allStatuses' },
  { value: 'pending', labelKey: 'statusPending' },
  { value: 'under_review', labelKey: 'statusUnderReview' },
  { value: 'approved', labelKey: 'statusApproved' },
  { value: 'rejected', labelKey: 'statusRejected' },
]

export default function StudentRequestsPage() {
  const { t } = useI18n()
  const [requests, setRequests] = useState<ReimbursementRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const data = await studentApi.getMyRequests(statusFilter || undefined)
        setRequests(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [statusFilter])

  const statusLabels: Record<RequestStatus, string> = {
    pending: t('statusPending'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
    under_review: t('statusUnderReview'),
  }

  return (
    <div>
      <Topbar title={t('requestsTitle')} />
      <div className="p-6 flex flex-col gap-4">

        {/* Header actions */}
        <div className="flex items-center justify-between">
          <div className="flex gap-2 flex-wrap">
            {STATUS_FILTERS.map(({ value, labelKey }) => (
              <button
                key={value}
                onClick={() => setStatusFilter(value)}
                className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-colors ${
                  statusFilter === value
                    ? 'bg-violet-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {t(labelKey)}
              </button>
            ))}
          </div>
          <Link href="/requests/submit">
            <Button variant="primary" size="sm">
              <PlusCircle className="h-4 w-4" />
              {t('submitRequest')}
            </Button>
          </Link>
        </div>

        {/* List */}
        {loading ? (
          <PageSpinner />
        ) : requests.length === 0 ? (
          <Card>
            <CardBody className="text-center py-12">
              <FileText className="h-10 w-10 mx-auto mb-3 text-gray-300" />
              <p className="text-gray-500 font-medium">{t('noRequests')}</p>
              <p className="text-sm text-gray-400 mt-1 mb-4">{t('noRequestsDesc')}</p>
              <Link href="/requests/submit">
                <Button variant="primary" size="sm">
                  <PlusCircle className="h-4 w-4" />
                  {t('submitRequest')}
                </Button>
              </Link>
            </CardBody>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {requests.map((req) => (
              <Link key={req.request_id} href={`/requests/${req.request_id}`}>
                <Card className="hover:border-violet-200 hover:shadow-md transition-all cursor-pointer">
                  <CardBody className="flex items-center justify-between">
                    <div className="flex flex-col gap-1">
                      <p className="font-medium text-gray-900">Request #{req.request_id}</p>
                      <p className="text-xs text-gray-400">
                        {t('submittedOn')}: {formatDate(req.submit_timestamp)}
                      </p>
                      {req.admin_feedback && (
                        <p className="text-xs text-gray-500 mt-1">
                          💬 {req.admin_feedback}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <RequestStatusBadge
                        status={req.status}
                        label={statusLabels[req.status]}
                      />
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    </div>
                  </CardBody>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
