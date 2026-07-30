import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import PreferenceCenterPage from './pages/PreferenceCenterPage'
import DSARRequestPage from './pages/DSARRequestPage'
import ConsentHistoryPage from './pages/ConsentHistoryPage'
import LoginPage from './pages/LoginPage'
import VerifyPage from './pages/VerifyPage'
import { isAuthenticated } from './services/auth'

function RequireAuth() {
  return isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<PreferenceCenterPage />} />
        <Route path="/dsar" element={<DSARRequestPage />} />
        <Route path="/history" element={<ConsentHistoryPage />} />
      </Route>
    </Routes>
  )
}
