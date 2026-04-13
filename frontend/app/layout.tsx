import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { I18nProvider } from '@/hooks/useI18n'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Student Reimbursement Portal',
  description: 'Fast, transparent and secure reimbursement for public transport costs',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-50 text-gray-900`}>
        <I18nProvider>
          {children}
        </I18nProvider>
      </body>
    </html>
  )
}
