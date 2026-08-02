import { useState } from 'react'
import { AlertTriangle, FileWarning, Search, ShieldCheck } from 'lucide-react'
import {
  Alert, AlertDescription, Badge, Button, Card, CardContent, ConsentBadge, Dialog,
  DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
  EmptyState, Input, Label, Select, SelectContent, SelectItem, SelectTrigger,
  SelectValue, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader,
  TableRow, Textarea, cn, formatDate, formatRelative,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import {
  AdminConsent, useConsentSearch, useConsentTimeline, useOverrideConsent,
} from '../hooks/useAdmin'

const SOURCES = ['PMP', 'IDP', 'API', 'salesforce', 'hubspot', 'outreach', 'highspot']

export default function ConsentAdminPage() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('')
  const [source, setSource] = useState('')
  const [evidence, setEvidence] = useState('')
  const [selected, setSelected] = useState<AdminConsent | null>(null)
  const [override, setOverride] = useState<{ c: AdminConsent; to: string } | null>(null)
  const [reason, setReason] = useState('')

  const { data, isLoading } = useConsentSearch({
    subject_email: email, status, source,
    ...(evidence ? { has_evidence: evidence === 'yes' } : {}),
  })
  const { data: timeline } = useConsentTimeline(selected?.id ?? null)
  const doOverride = useOverrideConsent()

  const rows = data?.consents ?? []
  const missingEvidence = rows.filter((r) => !r.has_evidence).length

  return (
    <ConsoleShell>
      <PageHeader
        title="Consents"
        description="Every consent across every source system. Search by Data Principal, then inspect or override."
      />

      {missingEvidence > 0 && (
        <Alert variant="warning" className="mb-5">
          <FileWarning />
          <AlertDescription>
            {missingEvidence} of {rows.length} shown have no recorded notice version. These predate
            evidence capture — they are still valid consents, but the exact wording shown cannot be
            reproduced, which weakens them under DPDP s.6(10).
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Data Principal email</Label>
            <div className="relative">
              <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" />
              <Input className="w-[240px] pl-8" placeholder="starts with…"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Status</Label>
            <Select value={status || 'all'} onValueChange={(v) => setStatus(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="granted">Granted</SelectItem>
                <SelectItem value="withdrawn">Withdrawn</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Source</Label>
            <Select value={source || 'all'} onValueChange={(v) => setSource(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All sources</SelectItem>
                {SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Evidence</Label>
            <Select value={evidence || 'all'} onValueChange={(v) => setEvidence(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[160px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any</SelectItem>
                <SelectItem value="yes">Has notice version</SelectItem>
                <SelectItem value="no">Missing evidence</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {data && (
            <span className="text-muted-foreground ml-auto pb-2 text-sm">
              {data.total.toLocaleString()} matching
            </span>
          )}
        </CardContent>
      </Card>

      {isLoading ? <Skeleton className="h-72 rounded-xl" />
        : rows.length === 0 ? (
          <EmptyState icon={Search} title="No consents match"
            description="Try a shorter email prefix or clear the filters." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Data Principal</TableHead>
                    <TableHead>Purpose</TableHead>
                    <TableHead>Channel</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Evidence</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((c) => (
                    <TableRow key={c.id} className="cursor-pointer" onClick={() => setSelected(c)}>
                      <TableCell className="font-mono text-xs">{c.subject_email}</TableCell>
                      <TableCell>{c.purpose}</TableCell>
                      <TableCell className="text-muted-foreground text-xs">{c.channel}</TableCell>
                      <TableCell><ConsentBadge status={c.status} /></TableCell>
                      <TableCell>
                        {c.has_evidence ? (
                          <span className="text-muted-foreground text-xs">
                            v{c.notice_version}
                            {c.language_version && ` · ${c.language_version}`}
                          </span>
                        ) : (
                          <Badge variant="pending">none</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {c.source_system ?? '—'}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {formatRelative(c.withdrawn_at ?? c.granted_at ?? c.created_at)}
                      </TableCell>
                      <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                        <Button size="sm" variant="ghost"
                          onClick={() => setOverride({
                            c, to: c.status === 'granted' ? 'withdrawn' : 'granted',
                          })}>
                          Override
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

      {/* Detail / timeline */}
      <Dialog open={Boolean(selected)} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Consent record</DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {selected?.subject_email} · {selected?.purpose} · {selected?.channel}
            </DialogDescription>
          </DialogHeader>

          {timeline?.consent && (
            <div className="grid gap-2 rounded-lg border p-3 text-sm sm:grid-cols-2">
              <Field label="Status" value={<ConsentBadge status={timeline.consent.status} />} />
              <Field label="Legal basis" value={timeline.consent.legal_basis} />
              <Field label="Notice version"
                value={timeline.consent.notice_version ? `v${timeline.consent.notice_version}` : 'not recorded'} />
              <Field label="Language" value={timeline.consent.language_version ?? '—'} />
              <Field label="Capture mode"
                value={(timeline.consent.capture_mode ?? '').replace(/_/g, ' ')} />
              <Field label="Witness" value={timeline.consent.witness_name ?? '—'} />
            </div>
          )}

          <div className="max-h-72 space-y-2 overflow-y-auto">
            <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Change history
            </p>
            {timeline?.history?.map((h: Record<string, string>, i: number) => (
              <div key={i} className="border-l-2 py-1.5 pl-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium capitalize">{h.action.replace(/_/g, ' ')}</span>
                  {h.action === 'admin_override' && <Badge variant="pending">DPO override</Badge>}
                  <span className="text-muted-foreground text-xs">{formatDate(h.created_at)}</span>
                </div>
                <p className="text-muted-foreground text-xs">
                  {h.actor_email ?? h.actor_type}
                  {h.reason && ` · "${h.reason}"`}
                </p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Override */}
      <Dialog open={Boolean(override)} onOpenChange={(o) => { if (!o) { setOverride(null); setReason('') } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Override to {override?.to === 'granted' ? 'granted' : 'withdrawn'}
            </DialogTitle>
            <DialogDescription>
              Acting on behalf of <span className="font-mono">{override?.c.subject_email}</span> for{' '}
              {override?.c.purpose}.
            </DialogDescription>
          </DialogHeader>

          <Alert variant="warning">
            <AlertTriangle />
            <AlertDescription>
              This bypasses normal conflict resolution and is recorded permanently against your
              account. Under DPDP s.6(10) the Data Fiduciary must be able to justify it.
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <Label htmlFor="reason">Reason (required)</Label>
            <Textarea id="reason" rows={3} value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Written withdrawal request received by post on 28 July, scanned to record #4471" />
            <p className={cn('text-xs', reason.trim().length < 10 ? 'text-muted-foreground' : 'text-granted')}>
              {reason.trim().length < 10
                ? `${10 - reason.trim().length} more characters needed`
                : 'Sufficient detail'}
            </p>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => { setOverride(null); setReason('') }}>Cancel</Button>
            <Button
              variant={override?.to === 'withdrawn' ? 'destructive' : 'default'}
              disabled={reason.trim().length < 10 || doOverride.isPending}
              onClick={() => override && doOverride.mutate(
                { id: override.c.id, status: override.to, reason },
                { onSuccess: () => { setOverride(null); setReason('') } },
              )}
            >
              <ShieldCheck className="size-4" />
              Record override
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsoleShell>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-muted-foreground text-xs">{label}</p>
      <div className="mt-0.5">{value}</div>
    </div>
  )
}
