import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  ClipboardList, FileSearch, KeyRound, LayoutDashboard, LogOut,
  Moon, RectangleHorizontal, ShieldCheck, Sun, Webhook,
} from 'lucide-react'
import { Badge, Button, cn } from '@sentinel/ui'
import { currentUser, hasPermission, logout } from '../services/auth'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, perm: 'read:audit', end: true },
  { to: '/banner', label: 'Banners', icon: RectangleHorizontal, perm: 'read:banner' },
  { to: '/consent', label: 'Consents', icon: ClipboardList, perm: 'read:consent_admin' },
  { to: '/dsar', label: 'DSAR queue', icon: FileSearch, perm: 'read:dsar' },
  { to: '/audit', label: 'Audit trail', icon: ShieldCheck, perm: 'read:audit' },
  { to: '/webhooks', label: 'Integrations', icon: Webhook, perm: 'read:webhook' },
  { to: '/api-keys', label: 'API keys', icon: KeyRound, perm: 'read:webhook' },
]

function toggleTheme() {
  const root = document.documentElement
  const dark = root.classList.toggle('dark')
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const user = currentUser()

  return (
    <div className="bg-background flex min-h-screen">
      <aside className="bg-sidebar hidden w-56 shrink-0 flex-col border-r p-3 md:flex">
        <div className="flex items-center gap-2 px-2 py-3">
          <ShieldCheck className="text-primary size-[18px]" />
          <span className="font-semibold tracking-tight">Sentinel</span>
          <Badge variant="secondary" className="ml-auto text-[10px]">Internal</Badge>
        </div>

        <nav className="mt-2 flex flex-1 flex-col gap-0.5">
          {NAV.filter((i) => hasPermission(i.perm)).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50',
              )}>
              <Icon className="size-4" /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t pt-3">
          <div className="px-2 pb-2">
            <p className="truncate text-xs font-medium">{user?.name}</p>
            <p className="text-muted-foreground text-xs capitalize">{user?.role}</p>
          </div>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" className="flex-1" onClick={toggleTheme}>
              <Sun className="size-4 dark:hidden" />
              <Moon className="hidden size-4 dark:block" />
            </Button>
            <Button variant="ghost" size="sm" className="flex-1"
              onClick={async () => { await logout(); navigate('/login') }}>
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-x-hidden px-6 py-7 lg:px-9">{children}</main>
    </div>
  )
}

export function PageHeader({ title, description, action }: {
  title: string; description?: string; action?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground mt-1 text-sm">{description}</p>}
      </div>
      {action}
    </div>
  )
}
