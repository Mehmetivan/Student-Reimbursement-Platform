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
import { ArrowLeft, CheckCircle, XCircle, FileText, ExternalLink, Image } from 'lucide-react'
import type { ReimbursementRequest, RequestStatus, StudentDetail } from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AdminRequestDetailPage() {
  const { t } = useI18n()
  const params = useParams()
  const router = useRouter()
  const [request, setRequest] = useState<ReimbursementRequest | null>(null)
  const [student, setStudent] = useState<StudentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [decisionModal, setDecisionModal] = useState<'approve' | 'reject' | null>(null)
  const [note, setNote] = useState('')
  const [acting, setActing] = useState(false)
  const [viewingDoc, setViewingDoc] = useState<{ url: string; label: string } | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const all = await adminApi.getRequests()
        const found = all.find((r) => r.request_id === Number(params.id))
        if (found) {
          setRequest(found)
          // Fetch student documents separately
          const studentData = await adminApi.getStudent(found.student_id)
          setStudent(studentData)
        }
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

  const getFileUrl = (filePath: string) => `${BASE_URL}/${filePath}`

  const openDoc = (filePath: string, label: string) => {
    setViewingDoc({ url: getFileUrl(filePath), label })
  }

  if (loading) return <PageSpinner />
  if (!request) return <div className="p-6 text-gray-500">Request not found</div>

  const statusLabels: Record<RequestStatus, string> = {
    pending: t('statusPending'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const canDecide = request.status === 'pending'

  const docTypeLabel: Record<string, string> = {
    student_id_photo: 'Student ID',
    stpt_card: 'STPT Card',
    bank_proof: 'Bank Statement',
  }

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
              <p className="text-sm text-gray-500">Student</p>
              <p className="text-sm font-medium text-gray-900">
                {student?.name ?? `Student ${request.student_id}`}
              </p>
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

        {/* Receipt images */}
        {request.receipts.map((receipt) => (
          <Card key={receipt.receipt_id}>
            <CardHeader>
              <h3 className="font-semibold text-gray-900">Receipt</h3>
            </CardHeader>
            <CardBody>
              {receipt.file_path ? (
                <div className="flex flex-col gap-2">
                  <img
                    src={getFileUrl(receipt.file_path)}
                    alt="Receipt"
                    className="w-full rounded-xl border border-gray-100 object-contain max-h-72 cursor-pointer hover:opacity-90 transition-opacity"
                    onClick={() => openDoc(receipt.file_path!, 'Receipt')}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    className="self-start"
                    onClick={() => openDoc(receipt.file_path!, 'Receipt')}
                  >
                    <Image className="h-4 w-4" />
                    View Receipt
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-gray-400">Receipt image not available</p>
              )}
            </CardBody>
          </Card>
        ))}

        {/* Student documents */}
        {student?.documents && student.documents.length > 0 && (
          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900">Student Documents</h3>
              <p className="text-xs text-gray-400 mt-0.5">Click to view</p>
            </CardHeader>
            <CardBody className="flex flex-col gap-2">
              {student.documents.map((doc) => (
                <button
                  key={doc.document_id}
                  onClick={() => openDoc(doc.file_path, docTypeLabel[doc.document_type] ?? doc.document_type)}
                  className="flex items-center justify-between p-3 rounded-xl border border-gray-100 hover:border-violet-200 hover:bg-violet-50/30 transition-all text-left"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-violet-600" />
                    <span className="text-sm font-medium text-gray-700">
                      {docTypeLabel[doc.document_type] ?? doc.document_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-gray-400" />
                </button>
              ))}
            </CardBody>
          </Card>
        )}

        {/* Decision buttons */}
        {canDecide && (
          <div className="flex gap-2 flex-wrap">
            <Button variant="primary" onClick={() => setDecisionModal('approve')} className="flex-1">
              <CheckCircle className="h-4 w-4" /> {t('approveRequest')}
            </Button>
            <Button variant="danger" onClick={() => setDecisionModal('reject')} className="flex-1">
              <XCircle className="h-4 w-4" /> {t('rejectRequest')}
            </Button>
          </div>
        )}

        {/* Fraud analysis */}
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

      {/* Document / Receipt viewer modal */}
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

      {/* Decision modal */}
      <Modal
        open={!!decisionModal}
        onClose={() => { setDecisionModal(null); setNote('') }}
        title={decisionModal === 'approve' ? t('approveRequest') : t('rejectRequest')}
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
    </div>
  )
}
