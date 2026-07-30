import { FormEvent, useState } from 'react'
import { requestMagicLink } from '../services/auth'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [error, setError] = useState('')

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setState('sending')
    try {
      await requestMagicLink(email)
      setState('sent')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setError(status === 429 ? 'Too many requests — please wait a few minutes.' : 'Something went wrong. Please try again.')
      setState('error')
    }
  }

  if (state === 'sent') {
    return (
      <main style={styles.wrap}>
        <div style={styles.card}>
          <h1 style={styles.title}>Check your email</h1>
          <p style={styles.sub}>
            If <strong>{email}</strong> is valid, a sign-in link is on its way.
            It expires in 15 minutes and can be used once.
          </p>
          <button style={styles.linkBtn} onClick={() => setState('idle')}>
            Use a different email
          </button>
        </div>
      </main>
    )
  }

  return (
    <main style={styles.wrap}>
      <div style={styles.card}>
        <h1 style={styles.title}>Privacy Preferences</h1>
        <p style={styles.sub}>Enter your email and we'll send you a secure sign-in link. No password needed.</p>
        <form onSubmit={onSubmit}>
          <input
            style={styles.input}
            type="email"
            required
            autoFocus
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button style={styles.button} type="submit" disabled={state === 'sending'}>
            {state === 'sending' ? 'Sending…' : 'Email me a sign-in link'}
          </button>
        </form>
        {state === 'error' && <p style={styles.error}>{error}</p>}
      </div>
    </main>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg,#667eea,#764ba2)', fontFamily: 'system-ui, sans-serif' },
  card: { background: '#fff', borderRadius: 12, padding: '40px 36px', maxWidth: 420, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,.3)' },
  title: { margin: '0 0 8px', fontSize: 24, color: '#333' },
  sub: { margin: '0 0 24px', color: '#666', lineHeight: 1.5 },
  input: { width: '100%', padding: '12px 14px', fontSize: 16, border: '1px solid #ddd', borderRadius: 8, marginBottom: 12, boxSizing: 'border-box' },
  button: { width: '100%', padding: '12px 14px', fontSize: 16, fontWeight: 600, color: '#fff', background: '#667eea', border: 'none', borderRadius: 8, cursor: 'pointer' },
  linkBtn: { background: 'none', border: 'none', color: '#667eea', cursor: 'pointer', padding: 0, fontSize: 14 },
  error: { color: '#c0392b', marginTop: 12, fontSize: 14 },
}
