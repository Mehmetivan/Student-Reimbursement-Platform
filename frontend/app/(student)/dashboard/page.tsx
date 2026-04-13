'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { formatDate, getAccountStatusColor } from '@/lib/utils'
import { Card, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { AccountStatusBadge } from '@/components/ui/Badge'
import { PlusCircle, FileText, User, CheckCircle, Clock, XCircle, AlertCircle } from 'lucide-react'
import type { StudentProfile, ReimbursementRequest } from '@/types'

export default function StudentDashboard() {
  const { t } = useI18n()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [requests, setRequests] = useState<ReimbursementRequest[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [p, r] = await Promise.all([
          studentApi.getProfile(),
          studentApi.getMyRequests(),
        ])
        setProfile(p)
        setRequests(r)
      } catch {
        // handled by axios interceptor
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <PageSpinner />

  const statusLabels = {
    incomplete: t('statusIncomplete'),
    pending_approval: t('statusPendingApproval'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const stats = [
    {
      label: t('statusPending'),
      value: requests.filter((r) => r.status === 'pending').length,
      icon: Clock,
      color: 'bg-amber-50 text-amber-600',
    },
    {
      label: t('statusApproved'),
      value: requests.filter((r) => r.status === 'approved').length,
      icon: CheckCircle,
      color: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: t('statusRejected'),
      value: requests.filter((r) => r.status === 'rejected').length,
      icon: XCircle,
      color: 'bg-red-50 text-red-600',
    },
    {
      label: t('statusUnderReview'),
      value: requests.filter((r) => r.status === 'under_review').length,
      icon: AlertCircle,
      color: 'bg-blue-50 text-blue-600',
    },
  ]

  return (
    <div>
      <Topbar title={t('dashboard')} />
      <div className="p-6 flex flex-col gap-6">

        {/* Account status banner */}
        {profile && profile.account_status !== 'approved' && (
          <div className={`rounded-2xl border p-4 flex items-center gap-3 ${
            profile.account_status === 'incomplete' ? 'bg-amber-50 border-amber-200' :
            profile.account_status === 'pending_approval' ? 'bg-blue-50 border-blue-200' :
            'bg-red-50 border-red-200'
          }`}>
            <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-800">
                {profile.account_status === 'incomplete' && 'Complete your profile to start submitting requests'}
                {profile.account_status === 'pending_approval' && 'Your account is pending admin approval'}
                {profile.account_status === 'rejected' && 'Your account has been rejected. Please contact support.'}
              </p>
            </div>
            {profile.account_status === 'incomplete' && (
              <Link href="/profile">
                <Button size="sm" variant="secondary">Complete Profile</Button>
              </Link>
            )}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map(({ label, value, icon: Icon, color }) => (
            <Card key={label}>
              <CardBody className="flex flex-col gap-2">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${color}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <span className="text-2xl font-bold text-gray-900">{value}</span>
                <span className="text-xs text-gray-500">{label}</span>
              </CardBody>
            </Card>
          ))}
        </div>

        {/* Quick actions */}
        <Card>
          <CardBody>
            <p className="text-sm font-semibold text-gray-700 mb-4">Quick Actions</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Link href="/requests/submit">
                <div className="border border-gray-200 rounded-xl p-4 hover:border-violet-300 hover:bg-violet-50/50 transition-colors cursor-pointer">
                  <PlusCircle className="h-5 w-5 text-violet-600 mb-2" />
                  <p className="text-sm font-medium text-gray-900">{t('submitRequest')}</p>
                  <p className="text-xs text-gray-500 mt-0.5">Upload a receipt</p>
                </div>
              </Link>
              <Link href="/requests">
                <div className="border border-gray-200 rounded-xl p-4 hover:border-blue-300 hover:bg-blue-50/50 transition-colors cursor-pointer">
                  <FileText className="h-5 w-5 text-blue-600 mb-2" />
                  <p className="text-sm font-medium text-gray-900">{t('myRequests')}</p>
                  <p className="text-xs text-gray-500 mt-0.5">View your history</p>
                </div>
              </Link>
              <Link href="/profile">
                <div className="border border-gray-200 rounded-xl p-4 hover:border-emerald-300 hover:bg-emerald-50/50 transition-colors cursor-pointer">
                  <User className="h-5 w-5 text-emerald-600 mb-2" />
                  <p className="text-sm font-medium text-gray-900">{t('profile')}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {profile?.account_status ? statusLabels[profile.account_status] : ''}
                  </p>
                </div>
              </Link>
            </div>
          </CardBody>
        </Card>

        {/* Recent requests */}
        <Card>
          <CardBody>
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-semibold text-gray-700">Recent Requests</p>
              <Link href="/requests">
                <Button variant="ghost" size="sm">{t('viewDetails')} →</Button>
              </Link>
            </div>
            {requests.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">{t('noRequests')}</p>
                <p className="text-xs mt-1">{t('noRequestsDesc')}</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {requests.slice(0, 5).map((req) => (
                  <Link key={req.request_id} href={`/requests/${req.request_id}`}>
                    <div className="flex items-center justify-between p-3 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer">
                      <div>
                        <p className="text-sm font-medium text-gray-900">Request #{req.request_id}</p>
                        <p className="text-xs text-gray-400">{formatDate(req.submit_timestamp)}</p>
                      </div>
                      <AccountStatusBadge
                        status={req.status as never}
                        label={req.status}
                      />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

      </div>
    </div>
  )
}
