import { AlertTriangle, ArrowDownRight, ArrowUpRight, FileSearch, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  Alert, AlertDescription, AlertTitle, Button, Card, CardContent, CardDescription,
  CardHeader, CardTitle, Skeleton, cn,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import { ConsentTimeseries, GrantsByPurpose } from '../components/Charts'
import { useByPurpose, useOverview, useTimeseries } from '../hooks/useAdmin'

function Stat({ label, value, hint, tone }: {
  label: string; value: string | number; hint?: string
  tone?: 'granted' | 'pending' | 'withdrawn'
}) {
  return (
    <Card className="gap-2 py-5">
      <CardContent className="px-5">
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">{label}</p>
        <p className="mt-1.5 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        {hint && (
          <p className={cn('mt-0.5 text-xs',
            tone === 'granted' && 'text-granted',
            tone === 'pending' && 'text-pending',
            tone === 'withdrawn' && 'text-withdrawn',
            !tone && 'text-muted-foreground')}>{hint}</p>
        )}
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { data: overview, isLoading } = useOverview()
  const { data: ts } = useTimeseries(30)
  const { data: purposes } = useByPurpose()

  return (
    <ConsoleShell>
      <PageHeader title="Dashboard"
        description="Consent health, request queue, and system activity at a glance." />

      {overview && overview.dsar_overdue > 0 && (
        <Alert variant="destructive" className="mb-5">
          <AlertTriangle />
          <AlertTitle>{overview.dsar_overdue} overdue data request{overview.dsar_overdue === 1 ? '' : 's'}</AlertTitle>
          <AlertDescription>
            The statutory response deadline has passed. This is a reportable compliance failure.
            <Button asChild variant="link" size="sm" className="h-auto p-0">
              <Link to="/dsar">Open the queue →</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : overview && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Active consents" value={overview.active_consents.toLocaleString()}
            hint={`${overview.consents_7d.toLocaleString()} new this week`} tone="granted" />
          <Stat label="Opt-out rate" value={`${overview.opt_out_rate}%`}
            hint={`${overview.withdrawn_consents.toLocaleString()} withdrawn`} />
          <Stat label="Data subjects" value={overview.total_subjects.toLocaleString()} />
          <Stat label="Open requests" value={overview.open_dsar}
            hint={overview.dsar_due_soon > 0 ? `${overview.dsar_due_soon} due within 5 days` : 'None urgent'}
            tone={overview.dsar_due_soon > 0 ? 'pending' : undefined} />
        </div>
      )}

      <div className="mt-5 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base">Consent activity</CardTitle>
            <CardDescription>Grants and withdrawals over the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            {ts ? <ConsentTimeseries data={ts.series} /> : <Skeleton className="h-64" />}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Grants by purpose</CardTitle>
            <CardDescription>Where consent is concentrated</CardDescription>
          </CardHeader>
          <CardContent>
            {purposes ? <GrantsByPurpose data={purposes.purposes} /> : <Skeleton className="h-48" />}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Card>
          <CardContent className="flex items-center gap-3 py-1">
            <FileSearch className="text-muted-foreground size-4" />
            <div className="flex-1">
              <p className="text-sm font-medium">Review the DSAR queue</p>
              <p className="text-muted-foreground text-xs">Fulfil or decline outstanding requests</p>
            </div>
            <Button asChild size="sm" variant="outline"><Link to="/dsar">Open</Link></Button>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 py-1">
            <Users className="text-muted-foreground size-4" />
            <div className="flex-1">
              <p className="text-sm font-medium">Audit trail</p>
              <p className="text-muted-foreground text-xs">Every change, immutable and exportable</p>
            </div>
            <Button asChild size="sm" variant="outline"><Link to="/audit">Open</Link></Button>
          </CardContent>
        </Card>
      </div>
    </ConsoleShell>
  )
}
