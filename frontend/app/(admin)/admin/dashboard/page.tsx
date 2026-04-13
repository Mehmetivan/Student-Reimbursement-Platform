'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { adminApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardBody } from '@/components/ui/Card'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { RequestStatusBadge, AccountStatusBadge } from '@/components/ui/Badge'
import { Users, FileText, Clock, CheckCircle, ChevronRight } from 'lucide-react'
import type { StudentDetail, ReimbursementRequest } from '@/types'

export default function AdminDashboard() {
  const { t } = useI18n()
  const [students, setStudents] = useState<StudentDetail[]>([])
  const [requests, setRequests] = useState<ReimbursementRequest[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [s, r] = await Promise.all([
          adminApi.getStudents(),
          adminApi.getRequests(),
        ])
        setStudents(s)
        setRequests(r)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return <PageSpinner />

  const pendingAccounts = students.filter((s) => s.account_status === 'pending_approval').length
  const pendingRequests = requests.filter((r) => r.status === 'pending').length

  const stats = [
    { label: t('totalStudents'), value: students.length, icon: Users, color: 'bg-violet-50 text-violet-600' },
    { label: t('pendingAccounts'), value: pendingAccounts, icon: Clock, color: 'bg-amber-50 text-amber-600' },
    { label: t('totalRequests'), value: requests.length, icon: FileText, color: 'bg-blue-50 text-blue-600' },
    { label: t('pendingRequests'), value: pendingRequests, icon: CheckCircle, color: 'bg-emerald-50 text-emerald-600' },
  ]

  const pendingStudents = students.filter((s) => s.account_status === 'pending_approval').slice(0, 5)
  const recentRequests = requests.slice(0, 5)

  return (
    <div>
      <Topbar title={t('adminDashboard')} />
      <div className="p-6 flex flex-col gap-6">

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

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Pending accounts */}
          <Card>
            <CardBody>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-semibold text-gray-700">{t('pendingAccounts')}</p>
                <Link href="/admin/students?status=pending_approval" className="text-xs text-violet-600 hover:underline">
                  View all →
                </Link>
              </div>
              {pendingStudents.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No pending accounts</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {pendingStudents.map((student) => (
                    <Link key={student.student_id} href={`/admin/students/${student.student_id}`}>
                      <div className="flex items-center justify-between p-3 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{student.name ?? student.email}</p>
                          <p className="text-xs text-gray-400">{student.email}</p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {/* Recent requests */}
          <Card>
            <CardBody>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-semibold text-gray-700">Recent Requests</p>
                <Link href="/admin/requests" className="text-xs text-violet-600 hover:underline">
                  View all →
                </Link>
              </div>
              {recentRequests.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-4">No requests yet</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {recentRequests.map((req) => (
                    <Link key={req.request_id} href={`/admin/requests/${req.request_id}`}>
                      <div className="flex items-center justify-between p-3 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer">
                        <div>
                          <p className="text-sm font-medium text-gray-900">Request #{req.request_id}</p>
                          <p className="text-xs text-gray-400">{formatDate(req.submit_timestamp)}</p>
                        </div>
                        <RequestStatusBadge status={req.status} label={req.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        </div>

      </div>
    </div>
  )
}
