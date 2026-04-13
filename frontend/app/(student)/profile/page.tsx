'use client'
import { useEffect, useState } from 'react'
import { useI18n } from '@/hooks/useI18n'
import { studentApi } from '@/lib/api'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { FileUpload } from '@/components/ui/FileUpload'
import { Topbar } from '@/components/layout/Topbar'
import { PageSpinner } from '@/components/ui/Spinner'
import { AccountStatusBadge } from '@/components/ui/Badge'
import type { StudentProfile } from '@/types'

export default function ProfilePage() {
  const { t } = useI18n()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [iban, setIban] = useState('')
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [uploadingDoc, setUploadingDoc] = useState<string | null>(null)
  const [uploadResults, setUploadResults] = useState<Record<string, string>>({})

  useEffect(() => {
    const load = async () => {
      try {
        const p = await studentApi.getProfile()
        setProfile(p)
        setName(p.name ?? '')
        setIban(p.iban ?? '')
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
      setProfile(updated)
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
    try {
      let result: Record<string, unknown>
      if (type === 'student-id') result = await studentApi.uploadStudentId(file) as Record<string, unknown>
      else if (type === 'stpt-card') result = await studentApi.uploadStptCard(file) as Record<string, unknown>
      else result = await studentApi.uploadBankProof(file) as Record<string, unknown>

      // Refresh profile to get updated document status and stpt_id
      const updated = await studentApi.getProfile()
      setProfile(updated)

      if (type === 'stpt-card' && result.extracted_stpt_id) {
        setUploadResults((prev) => ({
          ...prev,
          stpt: `STPT ID extracted: ${result.extracted_stpt_id}`,
        }))
      }
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

              <Button
                type="submit"
                variant="primary"
                loading={saving}
                className="self-start"
              >
                {saving ? t('saving') : t('saveChanges')}
              </Button>
            </form>
          </CardBody>
        </Card>

        {/* Documents */}
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">{t('documentsSection')}</h2>
            <p className="text-xs text-gray-400 mt-0.5">All 3 documents are required before your account can be approved</p>
          </CardHeader>
          <CardBody className="flex flex-col gap-5">
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

      </div>
    </div>
  )
}
