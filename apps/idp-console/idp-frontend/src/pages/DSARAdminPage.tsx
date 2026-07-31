import { useState } from 'react'
import { AlertTriangle, Download, FileJson, FileSpreadsheet, FileText, Loader2, XCircle } from 'lucide-react'
import {
  Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, Dialog,
  DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
  EmptyState, Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
  Skeleton, Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
  Textarea, cn, formatDate,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import { useDSARQueue, useDenyDSAR, useFulfilDSAR } from '../hooks/useAdmin'
import type { DSARQueueItem } from '../types'

const STATUS: Record<string, 'granted' | 'pending' | 'withdrawn' | 'secondary'> = {
  submitted: 'pending', acknowledged: 'pending', in_progress: 'pending',
  fulfilled: 'granted', denied: 'withdrawn', cancelled: 'secondary',
}

const FORMATS = [
  { value: 'json', label: 'JSON', icon: FileJson, hint: 'Machine-readable — the Art. 20 portability format' },
  { value: 'csv', label: 'CSV', icon: FileSpreadsheet, hint: 'Opens in any spreadsheet' },
  { value: 'pdf', label: 'PDF', icon: FileText, hint: 'Human-readable, for posting or archiving' },
]

export default function DSARAdminPage() {
  const [filter, setFilter] = useState<string>('')
  const { data, isLoading } = useDSARQueue(filter || undefined)
  const fulfil = useFulfilDSAR()
  const deny = useDenyDSAR()
  const [target, setTarget] = useState<DSARQueueItem | null>(null)
  const [format, setFormat] = useState('json')
  const [denying, setDenying] = useState<DSARQueueItem | null>(null)
  const [reason, setReason] = useState('')

  const requests = data?.requests ?? []

  return (
    <ConsoleShell>
      <PageHeader title="Data subject requests"
        description="Statutory deadline is 30 days. The queue is ordered by urgency — overdue first." />

      {data && data.overdue > 0 && (
        <Alert variant="destructive" className="mb-5">
          <AlertTriangle />
          <AlertTitle>{data.overdue} request{data.overdue === 1 ? '' : 's'} past the deadline</AlertTitle>
          <AlertDescription>
            Missing the statutory window is itself a reportable breach. Resolve these first.
          </AlertDescription>
        </Alert>
      )}

      <div className="mb-4 flex items-center gap-2">
        <Select value={filter || 'all'} onValueChange={(v) => setFilter(v === 'all' ? '' : v)}>
          <SelectTrigger className="w-[190px]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All requests</SelectItem>
            <SelectItem value="submitted">Submitted</SelectItem>
            <SelectItem value="in_progress">In progress</SelectItem>
            <SelectItem value="fulfilled">Fulfilled</SelectItem>
            <SelectItem value="denied">Declined</SelectItem>
          </SelectContent>
        </Select>
        {data && data.due_soon > 0 && (
          <Badge variant="pending">{data.due_soon} due within 5 days</Badge>
        )}
      </div>

      {isLoading ? <Skeleton className="h-64 rounded-xl" />
        : requests.length === 0 ? (
          <EmptyState icon={FileText} title="Queue is clear"
            description="No requests match this filter." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {requests.map((r) => (
                    <TableRow key={r.id} className={cn(r.is_overdue && 'bg-destructive/5')}>
                      <TableCell className="font-mono text-xs">{r.subject_email}</TableCell>
                      <TableCell className="capitalize">{r.request_type}</TableCell>
                      <TableCell><Badge variant={STATUS[r.status] ?? 'secondary'}>{r.status}</Badge></TableCell>
                      <TableCell className="text-muted-foreground text-xs">{formatDate(r.submitted_at)}</TableCell>
                      <TableCell>
                        {r.is_overdue ? (
                          <span className="text-destructive text-xs font-medium">Overdue</span>
                        ) : (
                          <span className={cn('text-xs', r.days_remaining <= 5 ? 'text-pending font-medium' : 'text-muted-foreground')}>
                            {r.days_remaining}d left
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {!['fulfilled', 'denied', 'cancelled'].includes(r.status) && (
                          <div className="flex justify-end gap-1.5">
                            <Button size="sm" variant="outline" onClick={() => setTarget(r)}>
                              <Download className="size-3.5" /> Fulfil
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setDenying(r)}>
                              <XCircle className="size-3.5" />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

      {/* Fulfil */}
      <Dialog open={Boolean(target)} onOpenChange={(o) => !o && setTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Fulfil request</DialogTitle>
            <DialogDescription>
              Generates the full export for {target?.subject_email} and marks the request complete.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>Format</Label>
            {FORMATS.map(({ value, label, icon: Icon, hint }) => (
              <button key={value} onClick={() => setFormat(value)}
                className={cn('flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                  format === value ? 'border-primary bg-accent' : 'hover:bg-muted/50')}>
                <Icon className="text-muted-foreground mt-0.5 size-4" />
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-muted-foreground text-xs">{hint}</p>
                </div>
              </button>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(null)}>Cancel</Button>
            <Button disabled={fulfil.isPending}
              onClick={() => target && fulfil.mutate({ id: target.id, format },
                { onSuccess: () => setTarget(null) })}>
              {fulfil.isPending && <Loader2 className="size-4 animate-spin" />}
              Generate export
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deny */}
      <Dialog open={Boolean(denying)} onOpenChange={(o) => !o && setDenying(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Decline request</DialogTitle>
            <DialogDescription>
              The reason is shown to the data subject and permanently recorded. Declining a valid
              request is unlawful — be specific about the exemption you are relying on.
            </DialogDescription>
          </DialogHeader>
          <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Duplicate of request #1234 submitted 3 days ago (Art. 12(5)(b) — manifestly excessive)" />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDenying(null)}>Cancel</Button>
            <Button variant="destructive" disabled={reason.length < 10 || deny.isPending}
              onClick={() => denying && deny.mutate({ id: denying.id, reason },
                { onSuccess: () => { setDenying(null); setReason('') } })}>
              Decline request
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsoleShell>
  )
}
