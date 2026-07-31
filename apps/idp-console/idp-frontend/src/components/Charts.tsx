import { useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { Table2, TrendingUp } from 'lucide-react'
import {
  Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@sentinel/ui'

/** Reads a CSS custom property so charts follow light/dark automatically. */
function token(name: string) {
  if (typeof window === 'undefined') return '#666'
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#666'
}

const axis = {
  stroke: 'var(--muted-foreground)',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-popover rounded-lg border px-3 py-2 text-xs shadow-md">
      <p className="text-muted-foreground mb-1.5 font-medium">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 py-0.5">
          <span className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto font-medium tabular-nums">{p.value.toLocaleString()}</span>
        </p>
      ))}
    </div>
  )
}

/**
 * Consent activity over time.
 * Two series whose colours were validated with the dataviz palette checker:
 * the badge emerald/rose pair is indistinguishable under deuteranopia
 * (ΔE 0.3), so the chart pair is re-stepped for lightness (ΔE 24.7).
 * Ships legend + table view as the mandated relief for the light-mode
 * contrast warning.
 */
export function ConsentTimeseries({ data }: {
  data: { date: string; granted: number; withdrawn: number }[]
}) {
  const [asTable, setAsTable] = useState(false)

  if (asTable) {
    return (
      <>
        <ViewToggle asTable onToggle={() => setAsTable(false)} />
        <Table>
          <TableHeader>
            <TableRow><TableHead>Date</TableHead><TableHead>Granted</TableHead><TableHead>Withdrawn</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.date}>
                <TableCell>{d.date}</TableCell>
                <TableCell className="tabular-nums">{d.granted}</TableCell>
                <TableCell className="tabular-nums">{d.withdrawn}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </>
    )
  }

  return (
    <>
      <ViewToggle asTable={false} onToggle={() => setAsTable(true)} />
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid stroke={token('--chart-grid')} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" {...axis} minTickGap={28}
            tickFormatter={(v: string) => v.slice(5)} />
          <YAxis {...axis} width={44} allowDecimals={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: token('--chart-grid') }} />
          <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          <Line type="monotone" dataKey="granted" name="Granted"
            stroke={token('--chart-granted')} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          <Line type="monotone" dataKey="withdrawn" name="Withdrawn"
            stroke={token('--chart-withdrawn')} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

/** Grant counts by purpose — magnitude, so a single hue. Colouring bars by
 *  rank would imply a categorical difference that isn't in the data. */
export function GrantsByPurpose({ data }: {
  data: { purpose: string; granted: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 42)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={token('--chart-grid')} strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" {...axis} allowDecimals={false} />
        <YAxis type="category" dataKey="purpose" {...axis} width={112} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'transparent' }} />
        <Bar dataKey="granted" name="Granted" fill={token('--chart-seq-3')}
          radius={[0, 4, 4, 0]} barSize={18}
          label={{ position: 'right', fontSize: 11, fill: 'var(--muted-foreground)' }} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function ViewToggle({ asTable, onToggle }: { asTable: boolean; onToggle: () => void }) {
  return (
    <div className="mb-2 flex justify-end">
      <Button variant="ghost" size="sm" onClick={onToggle} className="text-muted-foreground h-7">
        {asTable ? <><TrendingUp className="size-3.5" /> Chart</> : <><Table2 className="size-3.5" /> Table</>}
      </Button>
    </div>
  )
}
