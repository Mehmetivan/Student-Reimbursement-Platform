'use client'
import Link from 'next/link'
import { useI18n } from '@/hooks/useI18n'
import { Logo } from '@/components/ui/Logo'
import { Button } from '@/components/ui/Button'
import { LanguageToggle } from '@/components/features/LanguageToggle'
import { UserPlus, Upload, CheckCircle, Banknote, ArrowRight, Shield, Zap, Eye } from 'lucide-react'

export default function LandingPage() {
  const { t } = useI18n()

  const steps = [
    { icon: UserPlus, titleKey: 'landingStep1Title' as const, descKey: 'landingStep1Desc' as const, color: 'bg-violet-100 text-violet-600' },
    { icon: Upload, titleKey: 'landingStep2Title' as const, descKey: 'landingStep2Desc' as const, color: 'bg-blue-100 text-blue-600' },
    { icon: CheckCircle, titleKey: 'landingStep3Title' as const, descKey: 'landingStep3Desc' as const, color: 'bg-emerald-100 text-emerald-600' },
    { icon: Banknote, titleKey: 'landingStep4Title' as const, descKey: 'landingStep4Desc' as const, color: 'bg-amber-100 text-amber-600' },
  ]

  const features = [
    { icon: Shield, title: 'Automated Fraud Detection', desc: '5-layer validation system checks every receipt automatically.' },
    { icon: Zap, title: 'Fast Processing', desc: 'Receipts are analysed in seconds using multi-engine OCR.' },
    { icon: Eye, title: 'Full Transparency', desc: 'Track your request status and see detailed feedback from staff.' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <nav className="bg-white border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Logo size="md" />
          <div className="flex items-center gap-3">
            <LanguageToggle />
            <Link href="/login">
              <Button variant="ghost" size="sm">{t('signIn')}</Button>
            </Link>
            <Link href="/register">
              <Button variant="primary" size="sm">{t('getStarted')}</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 bg-violet-50 text-violet-700 px-3 py-1.5 rounded-full text-sm font-medium mb-6">
            <Shield className="h-3.5 w-3.5" />
            Student Reimbursement Platform
          </div>
          <h1 className="text-5xl font-bold text-gray-900 leading-tight mb-4">
            {t('landingTitle')}
          </h1>
          <p className="text-xl text-gray-500 mb-8 leading-relaxed">
            {t('landingSubtitle')}
          </p>
          <div className="flex items-center gap-4">
            <Link href="/register">
              <Button variant="primary" size="lg">
                {t('getStarted')}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button variant="secondary" size="lg">
                {t('signIn')}
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="bg-white border-y border-gray-100 py-16">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{t('landingHowItWorks')}</h2>
          <p className="text-gray-500 mb-10">Four simple steps to get reimbursed.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {steps.map(({ icon: Icon, titleKey, descKey, color }, i) => (
              <div key={i} className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-sm font-medium text-gray-400">Step {i + 1}</span>
                </div>
                <h3 className="font-semibold text-gray-900">{t(titleKey)}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{t(descKey)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map(({ icon: Icon, title, desc }, i) => (
            <div key={i} className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
              <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center text-violet-600 mb-4">
                <Icon className="h-5 w-5" />
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-violet-600 py-16">
        <div className="max-w-6xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to get started?</h2>
          <p className="text-violet-200 mb-8">Create your account and submit your first request today.</p>
          <Link href="/register">
            <Button variant="secondary" className="!bg-white hover:!bg-violet-50 border-white" size="lg" style={{ color: '#6d28d9' }}>
              {t('createAccount')}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between">
          <Logo size="sm" />
          <p className="text-sm text-gray-400">
            Student Reimbursement Portal
          </p>
        </div>
      </footer>
    </div>
  )
}
