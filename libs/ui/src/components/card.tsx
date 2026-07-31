import * as React from 'react'
import { cn } from '../lib/utils'

export const Card = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('bg-card text-card-foreground flex flex-col gap-6 rounded-xl border py-6 shadow-sm', className)} {...p} />
)
export const CardHeader = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('grid auto-rows-min items-start gap-1.5 px-6', className)} {...p} />
)
export const CardTitle = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('leading-none font-semibold tracking-tight', className)} {...p} />
)
export const CardDescription = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('text-muted-foreground text-sm', className)} {...p} />
)
export const CardAction = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('col-start-2 row-span-2 row-start-1 self-start justify-self-end', className)} {...p} />
)
export const CardContent = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('px-6', className)} {...p} />
)
export const CardFooter = ({ className, ...p }: React.ComponentProps<'div'>) => (
  <div className={cn('flex items-center px-6', className)} {...p} />
)
