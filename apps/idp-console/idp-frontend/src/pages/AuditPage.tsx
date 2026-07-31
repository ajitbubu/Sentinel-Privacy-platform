import { useState } from 'react'
import { Download, Lock, Search } from 'lucide-react'
import {
  Alert, AlertDescription, Badge, Button, Card, CardContent, EmptyState, Input,
  Label, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Skeleton,
  Switch, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, formatDate,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import { useAudit } from '../hooks/useAdmin'

const ENTITIES = ['consent', 'subject', 'banner', 'dsar', 'webhook', 'user', 'api_key']

export default function AuditPage() {
  const [entityType, setEntityType] = useState('')
  const [action, setAction] = useState('')
  const [gdprOnly, setGdprOnly] = useState(false)
  const [entityId, setEntityId] = useState('')

  const filters = { entity_type: entityType, action, gdpr_only: gdprOnly, entity_id: entityId }
  const { data, isLoading } = useAudit(filters)

  function exportCsv() {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, String(v)) })
    window.open(`/api/v1/admin/audit/export?${params}`, '_blank')
  }

  return (
    <ConsoleShell>
      <PageHeader title="Audit trail"
        description="Every change to consent, banners and requests. Append-only at the database level."
        action={<Button variant="outline" onClick={exportCsv}><Download className="size-4" /> Export CSV</Button>} />

      <Alert variant="info" className="mb-5">
        <Lock />
        <AlertDescription>
          This log cannot be edited or deleted — the database rejects UPDATE and DELETE on it,
          including from an administrator. That immutability is what makes it admissible evidence.
        </AlertDescription>
      </Alert>

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Entity</Label>
            <Select value={entityType || 'all'} onValueChange={(v) => setEntityType(v === 'all' ? '' : v)}>
              <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All entities</SelectItem>
                {ENTITIES.map((e) => <SelectItem key={e} value={e} className="capitalize">{e}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Action</Label>
            <Input className="w-[150px]" placeholder="granted, publish…"
              value={action} onChange={(e) => setAction(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Entity ID</Label>
            <Input className="w-[230px] font-mono text-xs" placeholder="uuid"
              value={entityId} onChange={(e) => setEntityId(e.target.value)} />
          </div>
          <div className="ml-auto flex items-center gap-2 pb-2">
            <Switch id="gdpr" checked={gdprOnly} onCheckedChange={setGdprOnly} />
            <Label htmlFor="gdpr" className="cursor-pointer text-xs">GDPR-relevant only</Label>
          </div>
        </CardContent>
      </Card>

      {isLoading ? <Skeleton className="h-72 rounded-xl" />
        : !data?.entries.length ? (
          <EmptyState icon={Search} title="No matching entries"
            description="Try widening the filters or clearing the entity ID." />
        ) : (
          <>
            <p className="text-muted-foreground mb-2 text-xs">
              {data.total.toLocaleString()} entries · showing {data.entries.length}
            </p>
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>When</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Actor</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.entries.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                          {formatDate(e.created_at)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="capitalize">{e.entity_type}</Badge>
                        </TableCell>
                        <TableCell className="text-sm capitalize">{e.action}</TableCell>
                        <TableCell className="text-xs">
                          {e.actor_email ?? e.actor_id?.slice(0, 8) ?? '—'}
                          <span className="text-muted-foreground ml-1.5">({e.actor_type})</span>
                        </TableCell>
                        <TableCell className="text-muted-foreground max-w-[260px] truncate text-xs">
                          {e.reason ?? '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        )}
    </ConsoleShell>
  )
}
