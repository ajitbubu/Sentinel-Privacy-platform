import { useState } from 'react'
import { Check, Clock, History, X } from 'lucide-react'
import {
  Badge, Card, CardContent, EmptyState, Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue, Skeleton, cn, formatDate,
} from '@sentinel/ui'
import { AppShell, PageHeader } from '../components/AppShell'
import { useConsentHistory } from '../hooks/useConsent'

const RANGES = [
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 3 months' },
  { value: '365', label: 'Last year' },
  { value: '3650', label: 'All time' },
]

export default function ConsentHistoryPage() {
  const [days, setDays] = useState('365')
  const { data, isLoading } = useConsentHistory(Number(days))
  const history = data?.history ?? []

  return (
    <AppShell>
      <PageHeader
        title="Your consent history"
        description="Every change to your preferences, with when it happened and where it came from. This record is permanent and cannot be edited — including by us."
      />

      <div className="mb-5 flex justify-end">
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-[170px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            {RANGES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
        </div>
      ) : history.length === 0 ? (
        <EmptyState
          icon={History}
          title="No changes in this period"
          description="Once you update your preferences, every change will appear here."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ol className="relative">
              {history.map((entry, i) => {
                const granted = entry.action === 'granted'
                return (
                  <li key={entry.id} className="flex gap-4 border-b px-5 py-4 last:border-0">
                    <div className="flex flex-col items-center">
                      <div className={cn(
                        'flex size-7 shrink-0 items-center justify-center rounded-full',
                        granted ? 'bg-granted-subtle text-granted' : 'bg-withdrawn-subtle text-withdrawn',
                      )}>
                        {granted ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                      </div>
                      {i < history.length - 1 && <div className="bg-border mt-1 w-px flex-1" />}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium">
                          {granted ? 'Granted' : 'Withdrawn'} · {entry.purpose}
                        </span>
                        <Badge variant="secondary">{entry.channel}</Badge>
                      </div>
                      <p className="text-muted-foreground mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                        <Clock className="size-3" />
                        {formatDate(entry.created_at)}
                        {entry.source_system && <>· via {entry.source_system}</>}
                        {entry.actor_type === 'system' && <>· automated sync</>}
                      </p>
                      {entry.reason && (
                        <p className="text-muted-foreground mt-1.5 text-xs italic">"{entry.reason}"</p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ol>
          </CardContent>
        </Card>
      )}
    </AppShell>
  )
}
