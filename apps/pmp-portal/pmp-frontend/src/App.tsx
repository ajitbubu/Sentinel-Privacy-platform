import { Routes, Route } from 'react-router-dom'
import PreferenceCenterPage from './pages/PreferenceCenterPage'
import DSARRequestPage from './pages/DSARRequestPage'
import ConsentHistoryPage from './pages/ConsentHistoryPage'
import LoginPage from './pages/LoginPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<PreferenceCenterPage />} />
      <Route path="/dsar" element={<DSARRequestPage />} />
      <Route path="/history" element={<ConsentHistoryPage />} />
    </Routes>
  )
}
