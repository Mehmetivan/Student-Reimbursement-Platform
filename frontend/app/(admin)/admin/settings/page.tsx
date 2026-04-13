'use client'
import { useI18n } from '@/hooks/useI18n'
import { Topbar } from '@/components/layout/Topbar'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'
import { api } from '@/lib/api'

export default function AdminSettingsPage() {
  const { t } = useI18n()
  const [current, setCurrent] = useState('')
  const [newPass, setNewPass] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPass !== confirm) {
      setMessage({ type: 'error', text: 'New passwords do not match' })
      return
    }
    setSaving(true)
    try {
      await api.patch('/auth/change-password', { current_password: current, new_password: newPass })
      setMessage({ type: 'success', text: 'Password changed successfully' })
      setCurrent(''); setNewPass(''); setConfirm('')
    } catch {
      setMessage({ type: 'error', text: 'Current password is incorrect' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <Topbar title={t('settings')} />
      <div className="p-6 max-w-md">
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900">{t('changePassword')}</h2>
          </CardHeader>
          <CardBody>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <Input label={t('currentPassword')} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
              <Input label={t('newPassword')} type="password" value={newPass} onChange={(e) => setNewPass(e.target.value)} required />
              <Input label={t('confirmPassword')} type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
              {message && (
                <div className={`rounded-xl px-4 py-3 text-sm border ${message.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-600' : 'bg-red-50 border-red-200 text-red-600'}`}>
                  {message.text}
                </div>
              )}
              <Button type="submit" variant="primary" loading={saving} className="self-start">{t('saveChanges')}</Button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
