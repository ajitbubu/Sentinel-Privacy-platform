import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import ApiKeysPage from './pages/ApiKeysPage'
import AuditPage from './pages/AuditPage'
import BannerBuilderPage from './pages/BannerBuilderPage'
import ConsentAdminPage from './pages/ConsentAdminPage'
import DSARAdminPage from './pages/DSARAdminPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import WebhooksPage from './pages/WebhooksPage'
import { hasPermission, isAuthenticated } from './services/auth'

function RequireAuth() {
  return isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />
}

function RequirePermission({ permission }: { permission: string }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (!hasPermission(permission)) {
    return (
      <main className="grid min-h-screen place-items-center p-10 text-center">
        <div>
          <h1 className="text-lg font-semibold">Access denied</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Your role does not include <code className="font-mono">{permission}</code>.
          </p>
        </div>
      </main>
    )
  }
  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<DashboardPage />} />
        <Route element={<RequirePermission permission="read:banner" />}>
          <Route path="/banner" element={<BannerBuilderPage />} />
        </Route>
        <Route element={<RequirePermission permission="read:consent_admin" />}>
          <Route path="/consent" element={<ConsentAdminPage />} />
        </Route>
        <Route element={<RequirePermission permission="read:dsar" />}>
          <Route path="/dsar" element={<DSARAdminPage />} />
        </Route>
        <Route element={<RequirePermission permission="read:audit" />}>
          <Route path="/audit" element={<AuditPage />} />
        </Route>
        <Route element={<RequirePermission permission="read:webhook" />}>
          <Route path="/webhooks" element={<WebhooksPage />} />
          <Route path="/api-keys" element={<ApiKeysPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
