import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../lib/utils'

const alertVariants = cva(
  'relative w-full rounded-lg border px-4 py-3 text-sm grid has-[>svg]:grid-cols-[calc(var(--spacing)*4)_1fr] grid-cols-[0_1fr] has-[>svg]:gap-x-3 gap-y-0.5 items-start [&>svg]:size-4 [&>svg]:translate-y-0.5',
  {
    variants: {
      variant: {
        default: 'bg-card text-card-foreground',
        info: 'bg-info-subtle border-info/25 text-foreground [&>svg]:text-info',
        warning: 'bg-pending-subtle border-pending/30 text-pending-foreground [&>svg]:text-pending',
        destructive: 'bg-card text-destructive [&>svg]:text-destructive border-destructive/30',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export function Alert({ className, variant, ...props }: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
}
export const AlertTitle = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('col-start-2 line-clamp-1 min-h-4 font-medium tracking-tight', className)} {...p} />
)
export const AlertDescription = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('text-muted-foreground col-start-2 grid justify-items-start gap-1 text-sm', className)} {...p} />
)
