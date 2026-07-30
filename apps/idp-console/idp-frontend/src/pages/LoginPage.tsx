import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, MfaRequired } from '../services/auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [needsMfa, setNeedsMfa] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password, needsMfa ? mfaCode : undefined)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (err instanceof MfaRequired) {
        setNeedsMfa(true)
        setError('')
      } else {
        const res = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response
        const detail = res?.data?.detail
        setError(
          res?.status === 423
            ? String(detail)
            : typeof detail === 'string'
              ? detail
              : 'Sign-in failed. Check your credentials.',
        )
        setMfaCode('')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <main style={s.wrap}>
      <form style={s.card} onSubmit={onSubmit}>
        <div style={s.badge}>INTERNAL</div>
        <h1 style={s.title}>IDP Console</h1>
        <p style={s.sub}>Data Protection Officer &amp; administration</p>

        <label style={s.label}>Email</label>
        <input
          style={s.input} type="email" required autoFocus value={email}
          disabled={needsMfa}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label style={s.label}>Password</label>
        <input
          style={s.input} type="password" required value={password}
          disabled={needsMfa}
          onChange={(e) => setPassword(e.target.value)}
        />

        {needsMfa && (
          <>
            <label style={s.label}>Authenticator code</label>
            <input
              style={{ ...s.input, letterSpacing: 8, fontSize: 20, textAlign: 'center' }}
              inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoFocus
              placeholder="000000" value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
            />
            <p style={s.hint}>Six-digit code from your authenticator app.</p>
          </>
        )}

        <button style={s.button} type="submit" disabled={busy}>
          {busy ? 'Verifying…' : needsMfa ? 'Verify code' : 'Sign in'}
        </button>

        {needsMfa && (
          <button
            type="button" style={s.linkBtn}
            onClick={() => { setNeedsMfa(false); setMfaCode(''); setError('') }}
          >
            Back
          </button>
        )}

        {error && <p style={s.error}>{error}</p>}
      </form>
    </main>
  )
}

const s: Record<string, React.CSSProperties> = {
  wrap: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#1a1a2e', fontFamily: 'system-ui, sans-serif' },
  card: { background: '#fff', borderRadius: 12, padding: '36px 34px', width: 400, boxShadow: '0 20px 60px rgba(0,0,0,.4)' },
  badge: { display: 'inline-block', fontSize: 11, fontWeight: 700, letterSpacing: 1, color: '#764ba2', background: '#f3f0fa', padding: '4px 8px', borderRadius: 4, marginBottom: 12 },
  title: { margin: '0 0 4px', fontSize: 24, color: '#222' },
  sub: { margin: '0 0 24px', color: '#666', fontSize: 14 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, color: '#444', marginBottom: 6 },
  input: { width: '100%', padding: '11px 13px', fontSize: 15, border: '1px solid #ddd', borderRadius: 8, marginBottom: 16, boxSizing: 'border-box' },
  hint: { fontSize: 12, color: '#888', marginTop: -10, marginBottom: 16 },
  button: { width: '100%', padding: '12px', fontSize: 15, fontWeight: 600, color: '#fff', background: '#764ba2', border: 'none', borderRadius: 8, cursor: 'pointer' },
  linkBtn: { width: '100%', marginTop: 10, background: 'none', border: 'none', color: '#764ba2', cursor: 'pointer', fontSize: 14 },
  error: { color: '#c0392b', marginTop: 14, marginBottom: 0, fontSize: 14 },
}
