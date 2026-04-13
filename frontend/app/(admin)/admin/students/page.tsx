'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { adminApi } from '@/lib/api'
import { Card, CardBody } from '@/components/ui/Card'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { AccountStatusBadge } from '@/components/ui/Badge'
import { ChevronRight, Search } from 'lucide-react'
import { Input } from '@/components/ui/Input'
import type { StudentDetail, AccountStatus } from '@/types'

const STATUS_FILTERS: { value: string; labelKey: 'allStatuses' | 'statusIncomplete' | 'statusPendingApproval' | 'statusApproved' | 'statusRejected' }[] = [
  { value: '', labelKey: 'allStatuses' },
  { value: 'incomplete', labelKey: 'statusIncomplete' },
  { value: 'pending_approval', labelKey: 'statusPendingApproval' },
  { value: 'approved', labelKey: 'statusApproved' },
  { value: 'rejected', labelKey: 'statusRejected' },
]

export default function AdminStudentsPage() {
  const { t } = useI18n()
  const [students, setStudents] = useState<StudentDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const data = await adminApi.getStudents(statusFilter || undefined)
        setStudents(data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [statusFilter])

  const statusLabels: Record<AccountStatus, string> = {
    incomplete: t('statusIncomplete'),
    pending_approval: t('statusPendingApproval'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const filtered = students.filter((s) =>
    !search ||
    s.email.toLowerCase().includes(search.toLowerCase()) ||
    s.name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <Topbar title={t('students')} />
      <div className="p-6 flex flex-col gap-4">

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3">
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
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              placeholder="Search by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500"
            />
          </div>
        </div>

        {/* Table */}
        {loading ? (
          <PageSpinner />
        ) : filtered.length === 0 ? (
          <Card>
            <CardBody className="text-center py-10 text-gray-400">No students found</CardBody>
          </Card>
        ) : (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('name')}</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('email')}</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('stptId')}</th>
                    <th className="text-left text-xs font-medium text-gray-400 px-6 py-3">{t('status')}</th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((student) => (
                    <tr key={student.student_id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">
                        {student.name ?? <span className="text-gray-400 italic">Not set</span>}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{student.email}</td>
                      <td className="px-6 py-4 text-sm font-mono text-gray-600">
                        {student.stpt_id ?? <span className="text-gray-400">—</span>}
                      </td>
                      <td className="px-6 py-4">
                        <AccountStatusBadge
                          status={student.account_status}
                          label={statusLabels[student.account_status]}
                        />
                      </td>
                      <td className="px-6 py-4">
                        <Link href={`/admin/students/${student.student_id}`}>
                          <button className="text-gray-400 hover:text-violet-600 transition-colors">
                            <ChevronRight className="h-4 w-4" />
                          </button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
