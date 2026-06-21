'use client'
import { useEffect, useState } from 'react'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { FileUpload } from '@/components/ui/FileUpload'
import { Modal } from '@/components/ui/Modal'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { AccountStatusBadge } from '@/components/ui/Badge'
import { FileText, ExternalLink } from 'lucide-react'
import type { StudentProfile } from '@/types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type StudentDocument = {
  document_id: string
  document_type: string
  file_path: string
  uploaded_at: string
}

export default function ProfilePage() {
  const { t } = useI18n()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [documents, setDocuments] = useState<StudentDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [iban, setIban] = useState('')
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [uploadingDoc, setUploadingDoc] = useState<string | null>(null)
  const [uploadResults, setUploadResults] = useState<Record<string, string>>({})
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [viewingDoc, setViewingDoc] = useState<{ url: string; label: string } | null>(null)

  const loadDocuments = async () => {
    try {
      const docs = await studentApi.getMyDocuments()
      setDocuments(docs)
    } catch {
      // no documents yet
    }
  }

  useEffect(() => {
    const load = async () => {
      try {
        const p = await studentApi.getProfile()
        setProfile(p)
        setName(p.name ?? '')
        setIban(p.iban ?? '')
        await loadDocuments()
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const updated = await studentApi.updateProfile({ name, iban })
      if (updated) setProfile(updated)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } finally {
      setSaving(false)
    }
  }

  const handleUpload = async (
    type: 'student-id' | 'stpt-card' | 'bank-proof',
    file: File
  ) => {
    setUploadingDoc(type)
    setUploadError(null)
    try {
      let result: Record<string, unknown>
      if (type === 'student-id') result = await studentApi.uploadStudentId(file) as Record<string, unknown>
      else if (type === 'stpt-card') result = await studentApi.uploadStptCard(file) as Record<string, unknown>
      else result = await studentApi.uploadBankProof(file) as Record<string, unknown>

      const updated = await studentApi.getProfile()
      setProfile(updated)
      await loadDocuments()

      if (type === 'stpt-card' && result.extracted_stpt_id) {
        setUploadResults((prev) => ({
          ...prev,
          stpt: `STPT ID extracted: ${result.extracted_stpt_id}`,
        }))
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setUploadError(detail || 'Upload failed')
    } finally {
      setUploadingDoc(null)
    }
  }

  if (loading) return <PageSpinner />

  const statusLabels = {
    incomplete: t('statusIncomplete'),
    pending_approval: t('statusPendingApproval'),
    approved: t('statusApproved'),
    rejected: t('statusRejected'),
  }

  const docTypeLabels: Record<string, string> = {
    STUDENT_ID: t('uploadStudentId'),
    STPT_CARD: t('uploadStptCard'),
    BANK_PROOF: t('uploadBankProof'),
  }

  return (
    <div>
      <Topbar title={t('profileTitle')} />
      <div className="p-6 flex flex-col gap-6 max-w-2xl">

        {/* Account status */}
        {profile && (
          <div className="flex items-center gap-3 bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
            <div>
              <p className="text-xs text-gray-400 mb-1">{t('accountStatus')}</p>
              <AccountStatusBadge
                status={profile.account_status}
                label={statusLabels[profile.account_status]}
              />
            </div>
            {profile.stpt_id && (
              <div className="ml-6">
                <p className="text-xs text-gray-400 mb-1">{t('stptId')}</p>
                <p className="text-sm font-mono font-medium text-gray-800">{profile.stpt_id}</p>
              </div>
            )}
          </div>
        )}

        {/* Profile form */}
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">Personal Information</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSaveProfile} className="flex flex-col gap-4">
              <Input
                label={t('email')}
                type="email"
                value={profile?.email ?? ''}
                disabled
                className="bg-gray-50 cursor-not-allowed"
              />
              <Input
                label={t('fullName')}
                placeholder="Ion Popescu"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Input
                label={t('iban')}
                placeholder="RO49AAAA1B31007593840000"
                value={iban}
                onChange={(e) => setIban(e.target.value)}
              />

              {saveSuccess && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-sm text-emerald-600">
                  Profile saved successfully
                </div>
              )}

              <Button type="submit" variant="primary" loading={saving} className="self-start">
                {saving ? t('saving') : t('saveChanges')}
              </Button>
            </form>
          </CardBody>
        </Card>

        {/* Documents upload */}
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">{t('documentsSection')}</h2>
            <p className="text-xs text-gray-400 mt-0.5">All 3 documents are required before your account can be approved</p>
          </CardHeader>
          <CardBody className="flex flex-col gap-5">
            {uploadError && (
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600">
                {uploadError}
              </div>
            )}
            <FileUpload
              label={t('uploadStudentId')}
              uploaded={profile?.documents_uploaded.student_id_photo ?? false}
              uploading={uploadingDoc === 'student-id'}
              uploadedLabel={t('uploaded')}
              notUploadedLabel={t('notUploaded')}
              clickToUploadLabel={t('clickToUpload')}
              onFileSelect={(file) => handleUpload('student-id', file)}
            />
            <FileUpload
              label={t('uploadStptCard')}
              uploaded={profile?.documents_uploaded.stpt_card ?? false}
              uploading={uploadingDoc === 'stpt-card'}
              uploadedLabel={t('uploaded')}
              notUploadedLabel={t('notUploaded')}
              clickToUploadLabel={t('clickToUpload')}
              onFileSelect={(file) => handleUpload('stpt-card', file)}
            />
            {uploadResults.stpt && (
              <p className="text-xs text-emerald-600 -mt-3">{uploadResults.stpt}</p>
            )}
            <FileUpload
              label={t('uploadBankProof')}
              uploaded={profile?.documents_uploaded.bank_proof ?? false}
              uploading={uploadingDoc === 'bank-proof'}
              uploadedLabel={t('uploaded')}
              notUploadedLabel={t('notUploaded')}
              clickToUploadLabel={t('clickToUpload')}
              onFileSelect={(file) => handleUpload('bank-proof', file)}
            />
          </CardBody>
        </Card>

        {/* View uploaded documents */}
        {documents.length > 0 && (
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-900">View Uploaded Documents</h2>
              <p className="text-xs text-gray-400 mt-0.5">Click to view your submitted documents</p>
            </CardHeader>
            <CardBody className="flex flex-col gap-2">
              {documents.map((doc) => (
                <button
                  key={doc.document_id}
                  onClick={() => setViewingDoc({ url: `${BASE_URL}/${doc.file_path}`, label: docTypeLabels[doc.document_type] ?? doc.document_type })}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-violet-50 hover:border hover:border-violet-200 transition-all w-full text-left"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-violet-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {docTypeLabels[doc.document_type] ?? doc.document_type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-gray-400">{doc.uploaded_at}</p>
                    </div>
                  </div>
                  <ExternalLink className="h-3.5 w-3.5 text-gray-400" />
                </button>
              ))}
            </CardBody>
          </Card>
        )}

      </div>

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
