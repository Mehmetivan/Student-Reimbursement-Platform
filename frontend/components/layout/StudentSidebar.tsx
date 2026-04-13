'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  User,
  FileText,
  PlusCircle,
  Settings,
  LogOut,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useI18n } from '@/hooks/useI18n'
import { useAuth } from '@/hooks/useAuth'
import { Logo } from '@/components/ui/Logo'

const navItems = [
  { href: '/dashboard', icon: LayoutDashboard, key: 'dashboard' as const },
  { href: '/profile', icon: User, key: 'profile' as const },
  { href: '/requests', icon: FileText, key: 'myRequests' as const },
  { href: '/requests/submit', icon: PlusCircle, key: 'submitRequest' as const },
  { href: '/settings', icon: Settings, key: 'settings' as const },
]

export function StudentSidebar() {
  const pathname = usePathname()
  const { t } = useI18n()
  const { currentUser, logout } = useAuth()

  return (
    <aside className="w-64 h-screen bg-white border-r border-gray-100 flex flex-col fixed left-0 top-0 z-40">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-100">
        <Logo />
      </div>

      {/* User info */}
      <div className="px-4 py-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-100 flex items-center justify-center text-violet-700 font-semibold text-sm">
            {currentUser?.email?.[0]?.toUpperCase() ?? 'S'}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-gray-900 truncate">
              {currentUser?.email}
            </span>
            <span className="text-xs text-emerald-500 font-medium">Online</span>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
        {navItems.map(({ href, icon: Icon, key }) => {
          const isActive = pathname === href || (href !== '/dashboard' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                isActive
                  ? 'bg-violet-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              )}
            >
              <Icon className="h-4 w-4 flex-shrink-0" />
              {t(key)}
            </Link>
          )
        })}
      </nav>

      {/* Logout */}
      <div className="px-3 py-4 border-t border-gray-100">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-500 hover:bg-red-50 w-full transition-colors"
        >
          <LogOut className="h-4 w-4" />
          {t('logout')}
        </button>
      </div>
    </aside>
  )
}
