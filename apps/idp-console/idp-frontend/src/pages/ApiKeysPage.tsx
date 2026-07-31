import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, Plus, ShieldAlert } from 'lucide-react'
import { toast } from 'sonner'
import {
  Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, Dialog,
  DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
  EmptyState, Input, Label, Select, SelectContent, SelectItem, SelectTrigger,
  SelectValue, Skeleton, Table, TableBody, TableCell, TableHead, TableHeader,
  TableRow, formatRelative,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import { api } from '../services/api'

interface ApiKey {
  id: string; name: string; client_system: string; key_prefix: string
  tier: string; is_active: boolean; last_used_at: string | null
  revoked_at: string | null; created_at: string
}

const SYSTEMS = ['salesforce', 'hubspot', 'outreach', 'highspot', 'custom']
const TIERS = [
  { value: 'standard', label: 'Standard — 100 req/min' },
  { value: 'premium', label: 'Premium — 1,000 req/min' },
  { value: 'enterprise', label: 'Enterprise — 10,000 req/min' },
]

export default function ApiKeysPage() {
  const qc = useQueryClient()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [system, setSystem] = useState('salesforce')
  const [tier, setTier] = useState('standard')
  const [issued, setIssued] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: async () => (await api.get<{ keys: ApiKey[] }>('/admin/api-keys')).data,
  })

  const create = useMutation({
    mutationFn: async () => (await api.post('/admin/api-keys', {
      name, client_system: system, tier,
    })).data,
    onSuccess: (r: { api_key: string }) => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      setIssued(r.api_key)
      setCreating(false)
      setName('')
    },
    onError: () => toast.error('Could not create the key'),
  })

  const revoke = useMutation({
    mutationFn: async (id: string) =>
      (await api.post(`/admin/api-keys/${id}/revoke`, { reason: 'Revoked from console' })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      toast.success('Key revoked — it stops working immediately')
    },
  })

  const keys = data?.keys ?? []

  return (
    <ConsoleShell>
      <PageHeader title="API keys"
        description="Server-side keys for partner systems submitting consent."
        action={<Button onClick={() => setCreating(true)}><Plus className="size-4" /> New key</Button>} />

      {isLoading ? <Skeleton className="h-48 rounded-xl" />
        : keys.length === 0 ? (
          <EmptyState icon={KeyRound} title="No API keys yet"
            description="Create a key so a partner system can submit consent." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead><TableHead>System</TableHead>
                    <TableHead>Key</TableHead><TableHead>Tier</TableHead>
                    <TableHead>Last used</TableHead><TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {keys.map((k) => (
                    <TableRow key={k.id}>
                      <TableCell className="font-medium">{k.name}</TableCell>
                      <TableCell className="capitalize">{k.client_system}</TableCell>
                      <TableCell className="font-mono text-xs">{k.key_prefix}…</TableCell>
                      <TableCell><Badge variant="secondary">{k.tier}</Badge></TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {k.last_used_at ? formatRelative(k.last_used_at) : 'Never'}
                      </TableCell>
                      <TableCell className="text-right">
                        {k.is_active ? (
                          <Button size="sm" variant="ghost" onClick={() => revoke.mutate(k.id)}>
                            Revoke
                          </Button>
                        ) : <Badge variant="withdrawn">Revoked</Badge>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API key</DialogTitle>
            <DialogDescription>
              The key is shown once. Store it in your secrets manager immediately.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="kname">Name</Label>
              <Input id="kname" value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Salesforce production" />
            </div>
            <div className="space-y-2">
              <Label>System</Label>
              <Select value={system} onValueChange={setSystem}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SYSTEMS.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Rate tier</Label>
              <Select value={tier} onValueChange={setTier}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TIERS.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button disabled={!name || create.isPending} onClick={() => create.mutate()}>
              Create key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(issued)} onOpenChange={(o) => !o && setIssued(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Your new API key</DialogTitle>
          </DialogHeader>
          <Alert variant="warning">
            <ShieldAlert />
            <AlertTitle>This is the only time you'll see it</AlertTitle>
            <AlertDescription>
              Only a hash is stored. If you lose it, revoke and issue a new one.
            </AlertDescription>
          </Alert>
          <div className="bg-muted flex items-center gap-2 rounded-lg p-3">
            <code className="flex-1 font-mono text-xs break-all">{issued}</code>
            <Button size="icon" variant="ghost" onClick={() => {
              navigator.clipboard.writeText(issued ?? '')
              toast.success('Copied')
            }}><Copy className="size-4" /></Button>
          </div>
          <DialogFooter>
            <Button onClick={() => setIssued(null)}>I've stored it</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsoleShell>
  )
}
