import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import BannerBuilderPage from './pages/BannerBuilderPage'
import ConsentAdminPage from './pages/ConsentAdminPage'
import DSARAdminPage from './pages/DSARAdminPage'
import AuditPage from './pages/AuditPage'
import WebhooksPage from './pages/WebhooksPage'
import LoginPage from './pages/LoginPage'
import { hasPermission, isAuthenticated } from './services/auth'

function RequireAuth() {
  return isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />
}

function RequirePermission({ permission }: { permission: string }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (!hasPermission(permission)) {
    return (
      <main style={{ padding: 40, fontFamily: 'system-ui, sans-serif' }}>
        <h1 style={{ fontSize: 20 }}>Access denied</h1>
        <p style={{ color: '#666' }}>Your role does not include <code>{permission}</code>.</p>
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
        <Route element={<RequirePermission permission="write:banner" />}>
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
        </Route>
      </Route>
    </Routes>
  )
}
