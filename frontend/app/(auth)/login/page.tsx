'use client'
import Link from 'next/link'
import { useState } from 'react'
import { useI18n } from '@/hooks/useI18n'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Card, CardBody } from '@/components/ui/Card'

export default function LoginPage() {
  const { t } = useI18n()
  const { login, loading, error } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await login(email, password)
  }

  return (
    <div className="w-full max-w-sm">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{t('login')}</h1>
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
              {loading ? t('loggingIn') : t('login')}
            </Button>
          </form>

          <p className="text-center text-sm text-gray-500">
            {t('noAccount')}{' '}
            <Link href="/register" className="text-violet-600 font-medium hover:underline">
              {t('createAccount')}
            </Link>
          </p>
        </CardBody>
      </Card>
    </div>
  )
}
