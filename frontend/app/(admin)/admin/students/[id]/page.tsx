'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useI18n } from '@/hooks/useI18n'
import { adminApi } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { AccountStatusBadge } from '@/components/ui/Badge'
import { ArrowLeft, CheckCircle, XCircle, FileText, Edit, ExternalLink } from 'lucide-react'
import type { StudentDetail, AccountStatus } from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AdminStudentDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [student, setStudent] = useState<StudentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | null>(null)
  const [editModal, setEditModal] = useState(false)
  const [note, setNote] = useState('')
  const [acting, setActing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editIban, setEditIban] = useState('')
  const [editStpt, setEditStpt] = useState('')
  const [viewingDoc, setViewingDoc] = useState<{ url: string; label: string } | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const data = await adminApi.getStudent(Number(params.id))
        setStudent(data)
        setEditName(data.name ?? '')
        setEditIban(data.iban ?? '')
        setEditStpt(data.stpt_id ?? '')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [params.id])

  const handleDecision = async () => {
    if (!decisionModal) return
    setActing(true)
    try {
      await adminApi.decideStudentAccount(Number(params.id), decisionModal, note)
      const updated = await adminApi.getStudent(Number(params.id))
      setStudent(updated)
      setDecisionModal(null)
      setNote('')
    } finally {
      setActing(false)
    }
  }

  const handleEdit = async () => {
    setActing(true)
    try {
      await adminApi.editStudent(Number(params.id), {
        name: editName || undefined,
        iban: editIban || undefined,
        stpt_id: editStpt || undefined,
      })
      const updated = await adminApi.getStudent(Number(params.id))
      setStudent(updated)
      setEditModal(false)
    } finally {
      setActing(false)
    }
  }

  if (loading) return <PageSpinner />
  if (!student) return <div className="p-6 text-gray-500">Student not found</div>

  const statusLabels: Record<AccountStatus, string> = {
    incomplete: t('statusIncomplete'),
    pending_approval: t('statusPendingApproval'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const docLabels: Record<string, string> = {
    STUDENT_ID: t('uploadStudentId'),
    STPT_CARD: t('uploadStptCard'),
    BANK_PROOF: t('uploadBankProof'),
  }

  return (
    <div>
      <Topbar title={student.name ?? student.email} />
      <div className="p-6 max-w-2xl flex flex-col gap-4">

        <Button variant="ghost" size="sm" onClick={() => router.push('/admin/students')} className="self-start">
          <ArrowLeft className="h-4 w-4" /> {t('students')}
        </Button>

        {/* Profile */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Student Profile</h2>
              <div className="flex items-center gap-2">
                <AccountStatusBadge status={student.account_status} label={statusLabels[student.account_status]} />
                <Button variant="secondary" size="sm" onClick={() => setEditModal(true)}>
                  <Edit className="h-3.5 w-3.5" />
                  {t('editStudent')}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {[
              { label: t('email'), value: student.email },
              { label: t('fullName'), value: student.name },
              { label: t('iban'), value: student.iban },
              { label: t('stptId'), value: student.stpt_id },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between py-1 border-b border-gray-50 last:border-0">
                <span className="text-sm text-gray-500">{label}</span>
                <span className="text-sm font-medium text-gray-900 font-mono">
                  {value ?? <span className="text-gray-400 font-sans italic">Not set</span>}
                </span>
              </div>
            ))}
          </CardBody>
        </Card>

        {/* Decision buttons */}
        {student.account_status === 'pending_approval' && (
          <div className="flex gap-3">
            <Button variant="primary" onClick={() => setDecisionModal('approve')} className="flex-1">
              <CheckCircle className="h-4 w-4" />
              {t('approveAccount')}
            </Button>
            <Button variant="danger" onClick={() => setDecisionModal('reject')} className="flex-1">
              <XCircle className="h-4 w-4" />
              {t('rejectAccount')}
            </Button>
          </div>
        )}

        {/* Documents */}
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">{t('documentsSection')}</h2>
            <p className="text-xs text-gray-400 mt-0.5">Click any document to view it</p>
          </CardHeader>
          <CardBody className="flex flex-col gap-3">
            {student.documents.length === 0 ? (
              <p className="text-sm text-gray-400">No documents uploaded yet</p>
            ) : (
              student.documents.map((doc) => (
                <button
                  key={doc.document_id}
                  onClick={() => setViewingDoc({ url: `${BASE_URL}/${doc.file_path}`, label: docLabels[doc.document_type] ?? doc.document_type })}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-violet-50 hover:border hover:border-violet-200 transition-all w-full text-left"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-violet-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{docLabels[doc.document_type] ?? doc.document_type}</p>
                      <p className="text-xs text-gray-400">{doc.uploaded_at}</p>
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-gray-400" />
                </button>
              ))
            )}
          </CardBody>
        </Card>

      </div>

      {/* Decision modal */}
      <Modal
        open={!!decisionModal}
        onClose={() => { setDecisionModal(null); setNote('') }}
        title={decisionModal === 'approve' ? t('approveAccount') : t('rejectAccount')}
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
              variant={decisionModal === 'approve' ? 'primary' : 'danger'}
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

      {/* Edit modal */}
      <Modal open={editModal} onClose={() => setEditModal(false)} title={t('editStudent')}>
        <div className="flex flex-col gap-4">
          <Input label={t('fullName')} value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input label={t('iban')} value={editIban} onChange={(e) => setEditIban(e.target.value)} />
          <Input label={t('stptId')} value={editStpt} onChange={(e) => setEditStpt(e.target.value)} />
          <div className="flex gap-3">
            <Button variant="primary" onClick={handleEdit} loading={acting} className="flex-1">
              {t('saveChanges')}
            </Button>
            <Button variant="secondary" onClick={() => setEditModal(false)} className="flex-1">
              {t('cancel')}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Document viewer modal */}
      <Modal
        open={!!viewingDoc}
        onClose={() => setViewingDoc(null)}
        title={viewingDoc?.label ?? 'Document'}
      >
        {viewingDoc && (
          <div className="flex flex-col gap-3">
            <img
              src={viewingDoc.url}
              alt={viewingDoc.label}
              className="w-full rounded-xl object-contain max-h-[70vh]"
            />
            <a
              href={viewingDoc.url}
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
