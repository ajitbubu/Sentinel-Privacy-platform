import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { verifyMagicLink } from '../services/auth'

export default function VerifyPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [state, setState] = useState<'verifying' | 'failed'>('verifying')
  const ran = useRef(false)  // React 18 StrictMode double-mount guard (token is single-use)

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    const token = params.get('token')
    if (!token) { setState('failed'); return }
    verifyMagicLink(token)
      .then(() => navigate('/', { replace: true }))
      .catch(() => setState('failed'))
  }, [params, navigate])

  return (
    <main style={wrap}>
      <div style={card}>
        {state === 'verifying' ? (
          <p style={{ color: '#666' }}>Signing you in…</p>
        ) : (
          <>
            <h1 style={{ fontSize: 20, color: '#333', marginTop: 0 }}>Link invalid or expired</h1>
            <p style={{ color: '#666' }}>Sign-in links expire after 15 minutes and work only once.</p>
            <a href="/login" style={{ color: '#667eea' }}>Request a new link</a>
          </>
        )}
      </div>
    </main>
  )
}

const wrap: React.CSSProperties = { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg,#667eea,#764ba2)', fontFamily: 'system-ui, sans-serif' }
const card: React.CSSProperties = { background: '#fff', borderRadius: 12, padding: '40px 36px', maxWidth: 420, textAlign: 'center', boxShadow: '0 20px 60px rgba(0,0,0,.3)' }
