import { FormEvent, useState } from 'react'
import { Loader2, MailCheck, ShieldCheck } from 'lucide-react'
import {
  Alert, AlertDescription, Button, Card, CardContent, CardDescription,
  CardHeader, CardTitle, Input, Label,
} from '@sentinel/ui'
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
      setError(status === 429
        ? 'Too many requests — please wait a few minutes.'
        : 'Something went wrong. Please try again.')
      setState('error')
    }
  }

  return (
    <div className="bg-muted/40 flex min-h-screen items-center justify-center p-5">
      <Card className="w-full max-w-md">
        {state === 'sent' ? (
          <>
            <CardHeader className="items-center text-center">
              <div className="bg-granted-subtle text-granted mb-2 flex size-11 items-center justify-center rounded-full">
                <MailCheck className="size-5" />
              </div>
              <CardTitle>Check your email</CardTitle>
              <CardDescription className="leading-relaxed">
                If <span className="text-foreground font-medium">{email}</span> is valid, a sign-in
                link is on its way. It expires in 15 minutes and works once.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="ghost" className="w-full" onClick={() => setState('idle')}>
                Use a different email
              </Button>
            </CardContent>
          </>
        ) : (
          <>
            <CardHeader>
              <div className="text-primary mb-1 flex items-center gap-2">
                <ShieldCheck className="size-5" />
                <span className="text-sm font-semibold tracking-tight">Privacy Centre</span>
              </div>
              <CardTitle>Sign in</CardTitle>
              <CardDescription>
                We'll email you a secure link. No password to remember or lose.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email address</Label>
                  <Input id="email" type="email" required autoFocus placeholder="you@example.com"
                    value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={state === 'sending'}>
                  {state === 'sending' && <Loader2 className="size-4 animate-spin" />}
                  Email me a sign-in link
                </Button>
                {state === 'error' && (
                  <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>
                )}
              </form>
            </CardContent>
          </>
        )}
      </Card>
    </div>
  )
}
