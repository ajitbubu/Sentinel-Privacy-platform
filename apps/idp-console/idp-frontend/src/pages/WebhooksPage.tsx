import { useQuery } from '@tanstack/react-query'
import { Activity, CheckCircle2, Webhook, XCircle } from 'lucide-react'
import {
  Alert, AlertDescription, Badge, Card, CardContent, CardDescription, CardHeader,
  CardTitle, EmptyState, Skeleton, Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow, cn,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import { api } from '../services/api'

interface Health {
  target_system: string; attempts: number; delivered: number
  failed: number; avg_latency_seconds: number | null
}

export default function WebhooksPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['webhook-health'],
    queryFn: async () => (await api.get<{ systems: Health[] }>(
      '/admin/analytics/webhook-health')).data,
    refetchInterval: 30_000,
  })

  const systems = data?.systems ?? []

  return (
    <ConsoleShell>
      <PageHeader title="Integrations"
        description="Outbound delivery health for every connected system, last 24 hours." />

      <Alert variant="info" className="mb-5">
        <Activity />
        <AlertDescription>
          Delivery is asynchronous with exponential backoff (1s→32s, 10 attempts) and a
          dead-letter queue. A slow partner never blocks a user-facing consent write.
        </AlertDescription>
      </Alert>

      {isLoading ? <Skeleton className="h-52 rounded-xl" />
        : systems.length === 0 ? (
          <EmptyState icon={Webhook} title="No integrations configured"
            description="Register a webhook to start syncing consent to your CRM." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {systems.map((s) => {
              const rate = s.attempts ? (s.delivered / s.attempts) * 100 : null
              const healthy = rate === null || rate >= 97
              return (
                <Card key={s.target_system}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base capitalize">{s.target_system}</CardTitle>
                      <Badge variant={healthy ? 'granted' : 'withdrawn'} className="gap-1">
                        {healthy ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
                        {rate === null ? 'Idle' : `${rate.toFixed(1)}%`}
                      </Badge>
                    </div>
                    <CardDescription>
                      {s.attempts === 0 ? 'No deliveries in the last 24h'
                        : `${s.delivered} of ${s.attempts} delivered`}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <p className="text-lg font-semibold tabular-nums">{s.delivered}</p>
                        <p className="text-muted-foreground text-xs">Delivered</p>
                      </div>
                      <div>
                        <p className={cn('text-lg font-semibold tabular-nums',
                          s.failed > 0 && 'text-withdrawn')}>{s.failed}</p>
                        <p className="text-muted-foreground text-xs">Failed</p>
                      </div>
                      <div>
                        <p className="text-lg font-semibold tabular-nums">
                          {s.avg_latency_seconds != null ? `${s.avg_latency_seconds}s` : '—'}
                        </p>
                        <p className="text-muted-foreground text-xs">Avg latency</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
    </ConsoleShell>
  )
}
