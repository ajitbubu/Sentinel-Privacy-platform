import { useEffect, useMemo, useState } from 'react'
import { Lock, Loader2, ShieldCheck } from 'lucide-react'
import {
  Alert, AlertDescription, AlertTitle, Badge, Button, Card, CardContent, CardHeader,
  Label, Separator, Skeleton, Switch, formatRelative,
} from '@sentinel/ui'
import { AppShell, PageHeader } from '../components/AppShell'
import { usePreferenceCentre, useUpdatePreferences } from '../hooks/useConsent'
import type { PurposeGroup } from '../types'

type Draft = Record<string, boolean> // `${purposeSlug}:${channel}` -> granted

function buildDraft(purposes: PurposeGroup[]): Draft {
  const d: Draft = {}
  for (const p of purposes) {
    for (const c of p.channels) d[`${p.slug}:${c.channel}`] = c.granted
  }
  return d
}

export default function PreferenceCenterPage() {
  const { data, isLoading } = usePreferenceCentre()
  const update = useUpdatePreferences()
  const [draft, setDraft] = useState<Draft>({})

  const purposes = data?.purposes ?? []

  // Re-sync the draft when server state changes (including via WebSocket),
  // but never clobber edits the user is in the middle of making.
  useEffect(() => {
    if (purposes.length && !update.isPending) setDraft(buildDraft(purposes))
  }, [data]) // eslint-disable-line react-hooks/exhaustive-deps

  const original = useMemo(() => buildDraft(purposes), [purposes])
  const changed = useMemo(
    () => Object.keys(draft).filter((k) => draft[k] !== original[k]),
    [draft, original],
  )

  function save() {
    update.mutate(changed.map((key) => {
      const [purpose, channel] = key.split(':')
      return { purpose, channel, granted: draft[key] }
    }))
  }

  function setAll(granted: boolean) {
    const next = { ...draft }
    for (const p of purposes) {
      if (p.is_mandatory) continue
      for (const c of p.channels) next[`${p.slug}:${c.channel}`] = granted
    }
    setDraft(next)
  }

  return (
    <AppShell>
      <PageHeader
        title="Your privacy preferences"
        description="Choose how we may contact you and what we may do with your data. Changes take effect immediately across every connected system."
      />

      {isLoading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)}
        </div>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setAll(true)}>Accept all</Button>
            <Button variant="outline" size="sm" onClick={() => setAll(false)}>Reject all optional</Button>
            <span className="text-muted-foreground ml-auto text-sm">
              {changed.length > 0
                ? `${changed.length} unsaved change${changed.length === 1 ? '' : 's'}`
                : 'All changes saved'}
            </span>
          </div>

          <div className="space-y-4">
            {purposes.map((p) => (
              <Card key={p.purpose_id}>
                <CardHeader className="pb-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{p.purpose}</span>
                        {p.is_mandatory && (
                          <Badge variant="secondary" className="gap-1">
                            <Lock className="size-3" /> Always on
                          </Badge>
                        )}
                      </div>
                      {p.description && (
                        <p className="text-muted-foreground text-sm leading-relaxed">{p.description}</p>
                      )}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-0">
                  <Separator className="mb-1" />
                  {p.channels.map((c) => {
                    const key = `${p.slug}:${c.channel}`
                    const disabled = p.is_mandatory
                    return (
                      <div key={c.channel_id} className="flex items-center justify-between gap-4 border-b py-3 last:border-0">
                        <div className="min-w-0">
                          <Label htmlFor={key} className={disabled ? 'opacity-60' : 'cursor-pointer'}>
                            {c.channel}
                          </Label>
                          <p className="text-muted-foreground mt-0.5 text-xs">
                            {c.status === 'granted' && c.granted_at && `Granted ${formatRelative(c.granted_at)}`}
                            {c.status === 'withdrawn' && c.withdrawn_at && `Withdrawn ${formatRelative(c.withdrawn_at)}`}
                            {c.status === 'pending' && 'No choice recorded yet'}
                            {c.source && c.status !== 'pending' && ` · via ${c.source}`}
                          </p>
                        </div>
                        <Switch
                          id={key}
                          checked={disabled ? true : (draft[key] ?? false)}
                          disabled={disabled}
                          onCheckedChange={(v) => setDraft((d) => ({ ...d, [key]: v }))}
                        />
                      </div>
                    )
                  })}
                  {p.retention_days && (
                    <p className="text-muted-foreground mt-3 text-xs">
                      Data for this purpose is kept for {p.retention_days} days after your last interaction.
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          <Alert variant="info" className="mt-6">
            <ShieldCheck />
            <AlertTitle>You can change these at any time</AlertTitle>
            <AlertDescription>
              Withdrawing consent is always available and takes effect immediately. It never
              affects your account or the service you receive.
            </AlertDescription>
          </Alert>
        </>
      )}

      {/* Save bar appears only when there's something to save */}
      {changed.length > 0 && (
        <div className="bg-card/95 sticky bottom-4 mt-6 flex items-center justify-between gap-4 rounded-xl border px-5 py-3 shadow-lg backdrop-blur">
          <span className="text-sm">
            {changed.length} unsaved change{changed.length === 1 ? '' : 's'}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setDraft(original)}>Discard</Button>
            <Button size="sm" onClick={save} disabled={update.isPending}>
              {update.isPending && <Loader2 className="size-4 animate-spin" />}
              Save preferences
            </Button>
          </div>
        </div>
      )}
    </AppShell>
  )
}
