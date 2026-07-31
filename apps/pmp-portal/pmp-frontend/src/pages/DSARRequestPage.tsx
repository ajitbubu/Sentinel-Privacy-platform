import { useState } from 'react'
import { Download, FileText, Loader2, Pencil, Trash2 } from 'lucide-react'
import {
  Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardDescription,
  CardHeader, CardTitle, EmptyState, Label, Skeleton, Textarea, cn, formatDate,
} from '@sentinel/ui'
import { AppShell, PageHeader } from '../components/AppShell'
import { useDSARRequests, useSubmitDSAR } from '../hooks/useDSAR'

const TYPES = [
  { value: 'access', label: 'Get a copy of my data', icon: FileText,
    blurb: 'Everything we hold about you, in JSON, CSV or PDF.' },
  { value: 'rectification', label: 'Correct my data', icon: Pencil,
    blurb: 'Tell us what is wrong and we will fix it.' },
  { value: 'portability', label: 'Transfer my data', icon: Download,
    blurb: 'A machine-readable export you can take elsewhere.' },
  { value: 'deletion', label: 'Delete my data', icon: Trash2,
    blurb: 'Erase your personal data where we are not legally required to keep it.' },
]

const STATUS: Record<string, { variant: 'granted' | 'pending' | 'withdrawn' | 'secondary'; label: string }> = {
  submitted:    { variant: 'pending',   label: 'Submitted' },
  acknowledged: { variant: 'pending',   label: 'Acknowledged' },
  in_progress:  { variant: 'pending',   label: 'In progress' },
  fulfilled:    { variant: 'granted',   label: 'Complete' },
  denied:       { variant: 'withdrawn', label: 'Declined' },
  cancelled:    { variant: 'secondary', label: 'Cancelled' },
}

export default function DSARRequestPage() {
  const { data, isLoading } = useDSARRequests()
  const submit = useSubmitDSAR()
  const [selected, setSelected] = useState<string | null>(null)
  const [description, setDescription] = useState('')

  const requests = data?.requests ?? []

  function send() {
    if (!selected) return
    submit.mutate(
      { request_type: selected, description: description || undefined },
      { onSuccess: () => { setSelected(null); setDescription('') } },
    )
  }

  return (
    <AppShell>
      <PageHeader
        title="Your data rights"
        description="You can ask for a copy of your data, correct it, take it elsewhere, or have it deleted. We respond within 30 days."
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        {TYPES.map(({ value, label, icon: Icon, blurb }) => {
          const active = selected === value
          const destructive = value === 'deletion'
          return (
            <button
              key={value}
              onClick={() => setSelected(active ? null : value)}
              className={cn(
                'rounded-xl border p-4 text-left transition-all',
                active ? 'border-primary ring-primary/25 ring-[3px]' : 'hover:border-foreground/20',
              )}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={cn('size-4', destructive ? 'text-withdrawn' : 'text-primary')} />
                <span className="text-sm font-medium">{label}</span>
              </div>
              <p className="text-muted-foreground mt-1.5 text-xs leading-relaxed">{blurb}</p>
            </button>
          )
        })}
      </div>

      {selected && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-base">
              {TYPES.find((t) => t.value === selected)?.label}
            </CardTitle>
            <CardDescription>
              Add any detail that will help us handle this correctly. Optional.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="detail">Details</Label>
              <Textarea
                id="detail" rows={3} value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={selected === 'rectification'
                  ? 'Which information is incorrect, and what should it say?'
                  : 'Anything else we should know?'}
              />
            </div>

            {selected === 'deletion' && (
              <Alert variant="warning">
                <Trash2 />
                <AlertTitle>Deletion is permanent</AlertTitle>
                <AlertDescription>
                  We'll erase your personal data except where law requires us to keep records —
                  for example, proof that you withdrew consent. We'll tell you exactly what was kept and why.
                </AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setSelected(null)}>Cancel</Button>
              <Button onClick={send} disabled={submit.isPending}
                variant={selected === 'deletion' ? 'destructive' : 'default'}>
                {submit.isPending && <Loader2 className="size-4 animate-spin" />}
                Submit request
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <h2 className="mb-3 text-sm font-semibold">Your requests</h2>
      {isLoading ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : requests.length === 0 ? (
        <EmptyState icon={FileText} title="No requests yet"
          description="When you make a request it will appear here so you can track its progress." />
      ) : (
        <div className="space-y-3">
          {requests.map((r) => {
            const s = STATUS[r.status] ?? { variant: 'secondary' as const, label: r.status }
            return (
              <Card key={r.id}>
                <CardContent className="flex flex-wrap items-center justify-between gap-3 py-1">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium capitalize">
                        {r.request_type.replace('_', ' ')}
                      </span>
                      <Badge variant={s.variant}>{s.label}</Badge>
                    </div>
                    <p className="text-muted-foreground mt-1 text-xs">
                      Submitted {formatDate(r.submitted_at)}
                      {r.status !== 'fulfilled' && r.days_remaining != null &&
                        ` · response due in ${r.days_remaining} days`}
                      {r.fulfilled_at && ` · completed ${formatDate(r.fulfilled_at)}`}
                    </p>
                    {r.denial_reason && (
                      <p className="text-muted-foreground mt-1 text-xs">Reason: {r.denial_reason}</p>
                    )}
                  </div>
                  {r.status === 'fulfilled' && (
                    <Button size="sm" variant="outline">
                      <Download className="size-4" /> Download
                    </Button>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </AppShell>
  )
}
