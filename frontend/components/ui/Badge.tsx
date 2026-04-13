import { cn } from '@/lib/utils'
import {
  getAccountStatusColor,
  getRequestStatusColor,
} from '@/lib/utils'
import type { AccountStatus, RequestStatus } from '@/types'

interface BadgeProps {
  label: string
  className?: string
}

export function Badge({ label, className }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium', className)}>
      {label}
    </span>
  )
}

export function AccountStatusBadge({
  status,
  label,
}: {
  status: AccountStatus
  label: string
}) {
  return (
    <Badge label={label} className={getAccountStatusColor(status)} />
  )
}

export function RequestStatusBadge({
  status,
  label,
}: {
  status: RequestStatus
  label: string
}) {
  return (
    <Badge label={label} className={getRequestStatusColor(status)} />
  )
}
