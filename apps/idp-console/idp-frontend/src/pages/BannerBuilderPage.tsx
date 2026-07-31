import { useEffect, useState } from 'react'
import { History, Loader2, Plus, Rocket, Save, Undo2 } from 'lucide-react'
import {
  Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardDescription,
  CardHeader, CardTitle, Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, EmptyState, Input, Label, Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue, Separator, Switch, Tabs, TabsContent, TabsList, TabsTrigger,
  Textarea, cn, formatRelative,
} from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'
import {
  useBanner, useBannerVersions, useBanners, usePublishBanner,
  useRollbackBanner, useSaveBanner,
} from '../hooks/useAdmin'
import type { Banner } from '../types'

const BLANK: Partial<Banner> = {
  name: '', slug: '', type: 'consent', title: 'We value your privacy',
  message: 'We use cookies and similar technologies to improve your experience, analyse traffic, and personalise content. You can change your choice at any time.',
  button_accept_text: 'Accept all', button_reject_text: 'Reject all',
  button_customize_text: 'Manage preferences',
  position: 'bottom', background_color: '#ffffff', text_color: '#333333',
  button_color: '#2f62d8', purposes: [], channels: [],
}

/** Renders the banner exactly as a visitor would see it. */
function BannerPreview({ draft }: { draft: Partial<Banner> }) {
  const modal = draft.position === 'modal'
  return (
    <div className={cn(
      'bg-muted/50 relative overflow-hidden rounded-lg border',
      modal ? 'grid min-h-[300px] place-items-center' : 'flex min-h-[300px] flex-col',
      draft.position === 'top' ? 'justify-start' : 'justify-end',
    )}>
      <div className="text-muted-foreground pointer-events-none absolute inset-0 grid place-items-center text-xs">
        customer website
      </div>
      <div
        className={cn('relative m-3 rounded-lg p-4 shadow-lg', modal && 'max-w-md')}
        style={{ background: draft.background_color, color: draft.text_color }}
      >
        {draft.title && <p className="mb-1.5 text-sm font-semibold">{draft.title}</p>}
        {draft.message && <p className="text-[13px] leading-relaxed opacity-90">{draft.message}</p>}
        <div className="mt-3.5 flex flex-wrap gap-2">
          {/* Reject is rendered with equal visual weight to accept — EEA guidance
              treats a de-emphasised reject as a dark pattern. */}
          <button className="rounded-md px-3 py-1.5 text-xs font-medium text-white"
            style={{ background: draft.button_color }}>
            {draft.button_accept_text}
          </button>
          <button className="rounded-md px-3 py-1.5 text-xs font-medium text-white"
            style={{ background: draft.button_color }}>
            {draft.button_reject_text}
          </button>
          <button className="rounded-md border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: draft.text_color, color: draft.text_color }}>
            {draft.button_customize_text}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function BannerBuilderPage() {
  const { data: list } = useBanners()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState<Partial<Banner>>(BLANK)
  const [material, setMaterial] = useState(false)
  const [note, setNote] = useState('')
  const [showVersions, setShowVersions] = useState(false)

  const { data: loaded } = useBanner(selectedId)
  const { data: versionData } = useBannerVersions(selectedId)
  const save = useSaveBanner(creating ? null : selectedId)
  const publish = usePublishBanner()
  const rollback = useRollbackBanner(selectedId ?? '')

  useEffect(() => { if (loaded && !creating) setDraft(loaded) }, [loaded, creating])

  const banners = list?.banners ?? []
  const set = (k: keyof Banner, v: unknown) => setDraft((d) => ({ ...d, [k]: v }))

  function onSave() {
    save.mutate({ ...draft, materially_changed: material, change_note: note || undefined },
      { onSuccess: (r: { id?: string }) => {
        if (creating && r?.id) { setSelectedId(r.id); setCreating(false) }
        setMaterial(false); setNote('')
      } })
  }

  return (
    <ConsoleShell>
      <PageHeader
        title="Banners"
        description="Author the notice shown on customer websites. Every save is versioned — the snapshot is what proves what a visitor agreed to."
        action={
          <Button onClick={() => { setCreating(true); setSelectedId(null); setDraft(BLANK) }}>
            <Plus className="size-4" /> New banner
          </Button>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[240px_1fr]">
        <div className="space-y-1.5">
          {banners.length === 0 && !creating ? (
            <EmptyState title="No banners yet" description="Create one to get started." />
          ) : banners.map((b) => (
            <button key={b.id}
              onClick={() => { setCreating(false); setSelectedId(b.id) }}
              className={cn('w-full rounded-lg border px-3 py-2.5 text-left transition-colors',
                selectedId === b.id ? 'border-primary bg-accent' : 'hover:bg-muted/50')}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">{b.name}</span>
                <Badge variant={b.status === 'published' ? 'granted' : 'secondary'}
                  className="shrink-0">{b.status}</Badge>
              </div>
              <p className="text-muted-foreground mt-0.5 text-xs">
                v{b.current_version} · {formatRelative(b.updated_at)}
              </p>
            </button>
          ))}
        </div>

        {(selectedId || creating) ? (
          <div className="space-y-4">
            <Tabs defaultValue="content">
              <TabsList>
                <TabsTrigger value="content">Content</TabsTrigger>
                <TabsTrigger value="style">Appearance</TabsTrigger>
                <TabsTrigger value="preview">Preview</TabsTrigger>
              </TabsList>

              <TabsContent value="content" className="mt-4">
                <Card>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="name">Internal name</Label>
                        <Input id="name" value={draft.name ?? ''}
                          onChange={(e) => set('name', e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="slug">Slug</Label>
                        <Input id="slug" value={draft.slug ?? ''} disabled={!creating}
                          placeholder="q3-2026-banner"
                          onChange={(e) => set('slug', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))} />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="title">Headline</Label>
                      <Input id="title" value={draft.title ?? ''}
                        onChange={(e) => set('title', e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="message">Notice text</Label>
                      <Textarea id="message" rows={4} value={draft.message ?? ''}
                        onChange={(e) => set('message', e.target.value)} />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {(['button_accept_text', 'button_reject_text', 'button_customize_text'] as const).map((k) => (
                        <div key={k} className="space-y-2">
                          <Label htmlFor={k} className="text-xs capitalize">
                            {k.replace('button_', '').replace('_text', '')}
                          </Label>
                          <Input id={k} value={(draft[k] as string) ?? ''}
                            onChange={(e) => set(k, e.target.value)} />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="style" className="mt-4">
                <Card>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>Position</Label>
                      <Select value={draft.position} onValueChange={(v) => set('position', v)}>
                        <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="bottom">Bottom bar</SelectItem>
                          <SelectItem value="top">Top bar</SelectItem>
                          <SelectItem value="modal">Centre modal</SelectItem>
                          <SelectItem value="sidebar">Sidebar</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {([['background_color', 'Background'], ['text_color', 'Text'],
                         ['button_color', 'Button']] as const).map(([k, label]) => (
                        <div key={k} className="space-y-2">
                          <Label className="text-xs">{label}</Label>
                          <div className="flex gap-2">
                            <input type="color" value={(draft[k] as string) ?? '#ffffff'}
                              onChange={(e) => set(k, e.target.value)}
                              className="border-input size-9 shrink-0 cursor-pointer rounded-md border bg-transparent" />
                            <Input value={(draft[k] as string) ?? ''} className="font-mono text-xs"
                              onChange={(e) => set(k, e.target.value)} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="preview" className="mt-4">
                <BannerPreview draft={draft} />
              </TabsContent>
            </Tabs>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Save this change</CardTitle>
                <CardDescription>
                  A material change forces everyone to consent again. Cosmetic edits should not.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-4 rounded-lg border p-3">
                  <div>
                    <Label htmlFor="material" className="cursor-pointer">Materially changed</Label>
                    <p className="text-muted-foreground mt-0.5 text-xs">
                      Turn on when purposes change or the meaning of the notice changes.
                    </p>
                  </div>
                  <Switch id="material" checked={material} onCheckedChange={setMaterial} />
                </div>
                {material && (
                  <Alert variant="warning">
                    <AlertTitle>This will re-prompt every visitor</AlertTitle>
                    <AlertDescription>
                      Existing consent becomes stale and the banner reappears for everyone.
                    </AlertDescription>
                  </Alert>
                )}
                <Input placeholder="Change note (appears in the version history)"
                  value={note} onChange={(e) => setNote(e.target.value)} />
                <Separator />
                <div className="flex flex-wrap gap-2">
                  <Button onClick={onSave} disabled={save.isPending}>
                    {save.isPending ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                    Save version
                  </Button>
                  {selectedId && (
                    <>
                      <Button variant="granted" onClick={() => publish.mutate(selectedId)}
                        disabled={publish.isPending}>
                        <Rocket className="size-4" /> Publish
                      </Button>
                      <Button variant="outline" onClick={() => setShowVersions(true)}>
                        <History className="size-4" /> History
                      </Button>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <EmptyState title="Select a banner"
            description="Choose one from the list, or create a new banner to begin." />
        )}
      </div>

      <Dialog open={showVersions} onOpenChange={setShowVersions}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Version history</DialogTitle>
            <DialogDescription>
              Each version is an immutable snapshot of what was shown to visitors.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-80 space-y-2 overflow-y-auto">
            {versionData?.versions.map((v) => (
              <div key={v.id} className="flex items-center gap-3 rounded-lg border p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">v{v.version}</span>
                    {v.is_current && <Badge variant="granted">Current</Badge>}
                    {v.materially_changed && <Badge variant="pending">Material</Badge>}
                  </div>
                  <p className="text-muted-foreground mt-0.5 truncate text-xs">
                    {v.change_description ?? 'No note'} · {v.changed_by ?? 'unknown'} · {formatRelative(v.created_at)}
                  </p>
                </div>
                {!v.is_current && (
                  <Button size="sm" variant="outline"
                    onClick={() => rollback.mutate(v.version, { onSuccess: () => setShowVersions(false) })}>
                    <Undo2 className="size-3.5" /> Restore
                  </Button>
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowVersions(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsoleShell>
  )
}
