import { Routes, Route } from 'react-router-dom'
import DashboardPage from './pages/DashboardPage'
import BannerBuilderPage from './pages/BannerBuilderPage'
import ConsentAdminPage from './pages/ConsentAdminPage'
import DSARAdminPage from './pages/DSARAdminPage'
import AuditPage from './pages/AuditPage'
import WebhooksPage from './pages/WebhooksPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/banners" element={<BannerBuilderPage />} />
      <Route path="/consents" element={<ConsentAdminPage />} />
      <Route path="/dsar" element={<DSARAdminPage />} />
      <Route path="/audit" element={<AuditPage />} />
      <Route path="/webhooks" element={<WebhooksPage />} />
    </Routes>
  )
}
