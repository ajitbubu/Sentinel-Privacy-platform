import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../lib/utils'

const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 gap-1 [&>svg]:size-3 transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        outline: 'text-foreground',
        destructive: 'border-transparent bg-destructive text-destructive-foreground',
        /* Consent states — see theme.css for why withdrawn is not red */
        granted: 'border-transparent bg-granted-subtle text-granted dark:text-granted-foreground',
        pending: 'border-transparent bg-pending-subtle text-pending-foreground',
        withdrawn: 'border-transparent bg-withdrawn-subtle text-withdrawn dark:text-withdrawn-foreground',
        info: 'border-transparent bg-info-subtle text-info',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export function Badge({ className, variant, ...props }: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

/** Maps a consent status string to the right badge. Single source of truth. */
export function ConsentBadge({ status }: { status: string }) {
  const map: Record<string, { variant: 'granted' | 'pending' | 'withdrawn' | 'secondary'; label: string }> = {
    granted:   { variant: 'granted',   label: 'Granted' },
    pending:   { variant: 'pending',   label: 'Pending' },
    withdrawn: { variant: 'withdrawn', label: 'Withdrawn' },
    expired:   { variant: 'secondary', label: 'Expired' },
    revoked:   { variant: 'withdrawn', label: 'Revoked' },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>
}

export { badgeVariants }
