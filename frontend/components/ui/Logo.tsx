import { cn } from '@/lib/utils'

export function Logo({ className, size = 'md' }: { className?: string; size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: { box: 28, text: 'text-sm' },
    md: { box: 36, text: 'text-base' },
    lg: { box: 44, text: 'text-lg' },
  }
  const s = sizes[size]

  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      {/* Geometric logo — two overlapping squares, similar to UVT style */}
      <svg width={s.box} height={s.box} viewBox="0 0 36 36" fill="none">
        <rect x="2" y="8" width="20" height="20" rx="4" fill="#7C3AED" opacity="0.9" />
        <rect x="14" y="2" width="20" height="20" rx="4" fill="#6D28D9" opacity="0.7" />
        <rect x="8" y="14" width="20" height="20" rx="4" fill="#4C1D95" opacity="0.5" />
        <text x="18" y="23" textAnchor="middle" fill="white" fontSize="11" fontWeight="700" fontFamily="system-ui">S</text>
      </svg>
      <div className="flex flex-col leading-tight">
        <span className={cn('font-bold text-gray-900', s.text)}>SRP</span>
        <span className="text-xs text-gray-400 hidden sm:block">Student Reimbursement</span>
      </div>
    </div>
  )
}
