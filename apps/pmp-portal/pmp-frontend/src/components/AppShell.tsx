import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Clock, FileText, LogOut, ShieldCheck, SlidersHorizontal, Wifi, WifiOff } from 'lucide-react'
import { Button, cn } from '@sentinel/ui'
import { logout } from '../services/auth'
import { useRealtimeSync } from '../hooks/useRealtimeSync'

const nav = [
  { to: '/', label: 'Preferences', icon: SlidersHorizontal, end: true },
  { to: '/history', label: 'History', icon: Clock },
  { to: '/dsar', label: 'My data', icon: FileText },
]

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { connected } = useRealtimeSync()

  return (
    <div className="bg-background min-h-screen">
      <header className="bg-card/80 sticky top-0 z-40 border-b backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-4xl items-center gap-6 px-5">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="text-primary size-[18px]" />
            <span className="tracking-tight">Privacy Centre</span>
          </div>

          <nav className="flex flex-1 items-center gap-1">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => cn(
                  'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:text-foreground',
                )}>
                <Icon className="size-4" />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>

          <div
            className="text-muted-foreground flex items-center gap-1.5 text-xs"
            title={connected ? 'Live — changes sync instantly' : 'Reconnecting…'}
          >
            {connected
              ? <Wifi className="text-granted size-3.5" />
              : <WifiOff className="size-3.5" />}
            <span className="hidden md:inline">{connected ? 'Live' : 'Offline'}</span>
          </div>

          <Button variant="ghost" size="icon" title="Sign out"
            onClick={async () => { await logout(); navigate('/login') }}>
            <LogOut className="size-4" />
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 py-8">{children}</main>
    </div>
  )
}

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-7">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="text-muted-foreground mt-1.5 text-[15px] leading-relaxed">{description}</p>}
    </div>
  )
}
