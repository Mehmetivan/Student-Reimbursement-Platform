'use client'
import Link from 'next/link'
import { useState } from 'react'
import { useI18n } from '@/hooks/useI18n'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardBody } from '@/components/ui/Card'

export default function RegisterPage() {
  const { t } = useI18n()
  const { register, loading, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }
    if (password.length < 8) {
      setPasswordError('Password must be at least 8 characters')
      return
    }
    setPasswordError('')
    await register(email, password)
  }

  return (
    <div className="w-full max-w-sm">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t('createAccount')}</h1>
        <p className="text-gray-500 text-sm mt-1">Student Reimbursement Portal</p>
      </div>

      <Card>
        <CardBody className="flex flex-col gap-4">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label={t('email')}
              type="email"
              placeholder="student@e-uvt.ro"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label={t('password')}
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Input
              label={t('confirmPassword')}
              type="password"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              error={passwordError}
              required
            />

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-1"
            >
              {loading ? t('registering') : t('createAccount')}
            </Button>
          </form>

          <p className="text-center text-sm text-gray-500">
            {t('hasAccount')}{' '}
            <Link href="/login" className="text-violet-600 font-medium hover:underline">
              {t('login')}
            </Link>
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
