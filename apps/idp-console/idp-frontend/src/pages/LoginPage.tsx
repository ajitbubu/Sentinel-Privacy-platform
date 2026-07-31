import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ShieldCheck } from 'lucide-react'
import {
  Alert, AlertDescription, Badge, Button, Card, CardContent, CardDescription,
  CardHeader, CardTitle, Input, Label,
} from '@sentinel/ui'
import { MfaRequired, login } from '../services/auth'

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
    setBusy(true); setError('')
    try {
      await login(email, password, needsMfa ? mfaCode : undefined)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      if (err instanceof MfaRequired) { setNeedsMfa(true); setError('') }
      else {
        const res = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response
        const detail = res?.data?.detail
        setError(res?.status === 423 ? String(detail)
          : typeof detail === 'string' ? detail
          : 'Sign-in failed. Check your credentials.')
        setMfaCode('')
      }
    } finally { setBusy(false) }
  }

  return (
    <div className="bg-muted/40 flex min-h-screen items-center justify-center p-5">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-1 flex items-center gap-2">
            <ShieldCheck className="text-primary size-5" />
            <span className="font-semibold tracking-tight">Sentinel</span>
            <Badge variant="secondary" className="ml-auto text-[10px]">Internal</Badge>
          </div>
          <CardTitle>{needsMfa ? 'Two-factor authentication' : 'Console sign-in'}</CardTitle>
          <CardDescription>
            {needsMfa
              ? 'Enter the six-digit code from your authenticator app.'
              : 'Data protection officer and administration access.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            {!needsMfa ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" required autoFocus value={email}
                    onChange={(e) => setEmail(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input id="password" type="password" required value={password}
                    onChange={(e) => setPassword(e.target.value)} />
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="mfa">Authenticator code</Label>
                <Input id="mfa" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoFocus
                  placeholder="000000" value={mfaCode}
                  className="text-center font-mono text-lg tracking-[0.4em]"
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))} />
              </div>
            )}

            <Button type="submit" className="w-full" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" />}
              {needsMfa ? 'Verify' : 'Sign in'}
            </Button>

            {needsMfa && (
              <Button type="button" variant="ghost" className="w-full"
                onClick={() => { setNeedsMfa(false); setMfaCode(''); setError('') }}>
                Back
              </Button>
            )}

            {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
