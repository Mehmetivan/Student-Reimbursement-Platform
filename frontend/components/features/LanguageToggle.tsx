'use client'
import { useI18n } from '@/hooks/useI18n'

export function LanguageToggle() {
  const { lang, setLang } = useI18n()

  return (
    <button
      onClick={() => setLang(lang === 'en' ? 'ro' : 'en')}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-sm font-medium text-gray-600"
    >
      <span className="text-base">{lang === 'en' ? '🇬🇧' : '🇷🇴'}</span>
      <span>{lang.toUpperCase()}</span>
    </button>
  )
}
