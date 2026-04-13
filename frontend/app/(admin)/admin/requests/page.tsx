'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { adminApi } from '@/lib/api'
import { formatDate, formatRiskScore, getRiskColor } from '@/lib/utils'
import { Card, CardBody } from '@/components/ui/Card'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge } from '@/components/ui/Badge'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReimbursementRequest, RequestStatus } from '@/types'

const STATUS_FILTERS = ['', 'pending', 'under_review', 'approved', 'rejected']
const TIMEFRAME_OPTIONS = [
  { value: '', label: 'allTime' },
  { value: 'today', label: 'today' },
  { value: 'this_week', label: 'thisWeek' },
  { value: 'this_month', label: 'thisMonth' },
  { value: '3_months', label: 'threeMonths' },
  { value: '6_months', label: 'sixMonths' },
  { value: 'this_year', label: 'thisYear' },
] as const

export default function AdminRequestsPage() {
  const { t } = useI18n()
  const [requests, setRequests] = useState<ReimbursementRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [timeframe, setTimeframe] = useState('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const data = await adminApi.getRequests(statusFilter || undefined, timeframe || undefined)
        setRequests(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [statusFilter, timeframe])

  const statusLabels: Record<RequestStatus, string> = {
    pending: t('statusPending'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
    under_review: t('statusUnderReview'),
  }

  const statusFilterLabels: Record<string, string> = {
    '': t('allStatuses'),
    pending: t('statusPending'),
    under_review: t('statusUnderReview'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  return (
    <div>
      <Topbar title={t('requests')} />
      <div className="p-6 flex flex-col gap-4">

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 flex-wrap">
          <div className="flex gap-2 flex-wrap">
            {STATUS_FILTERS.map((value) => (
              <button
                key={value}
                onClick={() => setStatusFilter(value)}
                className={`px-3 py-1.5 rounded-xl text-sm font-medium transition-colors ${
                  statusFilter === value
                    ? 'bg-violet-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
              >
                {statusFilterLabels[value]}
              </button>
            ))}
          </div>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 bg-white focus:outline-none focus:ring-2 focus:ring-violet-500"
          >
            {TIMEFRAME_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{t(label)}</option>
            ))}
          </select>
        </div>

        {/* List */}
        {loading ? (
          <PageSpinner />
        ) : requests.length === 0 ? (
          <Card>
            <CardBody className="text-center py-10 text-gray-400">No requests found</CardBody>
          </Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">ID</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">Student</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('date')}</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('riskScore')}</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('status')}</th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((req) => {
                    const topRisk = req.receipts[0]?.risk_assessment?.total_risk_score
                    return (
                      <tr key={req.request_id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-4 text-sm font-medium text-gray-900">#{req.request_id}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">Student {req.student_id}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{formatDate(req.submit_timestamp)}</td>
                        <td className="px-6 py-4">
                          {topRisk !== undefined ? (
                            <span className={cn('text-sm font-bold', getRiskColor(topRisk))}>
                              {formatRiskScore(topRisk)}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-sm">—</span>
                          )}
                        </td>
                        <td className="px-6 py-4">
                          <RequestStatusBadge status={req.status} label={statusLabels[req.status]} />
                        </td>
                        <td className="px-6 py-4">
                          <Link href={`/admin/requests/${req.request_id}`}>
                            <button className="text-gray-400 hover:text-violet-600 transition-colors">
                              <ChevronRight className="h-4 w-4" />
                            </button>
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
