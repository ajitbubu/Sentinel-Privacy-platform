import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, TriangleAlert } from 'lucide-react'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sentinel/ui'
import { verifyMagicLink } from '../services/auth'

export default function VerifyPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  const ran = useRef(false) // StrictMode double-mount guard — the token is single-use

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    const token = params.get('token')
    if (!token) { setFailed(true); return }
    verifyMagicLink(token)
      .then(() => navigate('/', { replace: true }))
      .catch(() => setFailed(true))
  }, [params, navigate])

  return (
    <div className="bg-muted/40 flex min-h-screen items-center justify-center p-5">
      <Card className="w-full max-w-md">
        {failed ? (
          <>
            <CardHeader className="items-center text-center">
              <div className="bg-pending-subtle text-pending mb-2 flex size-11 items-center justify-center rounded-full">
                <TriangleAlert className="size-5" />
              </div>
              <CardTitle>This link has expired</CardTitle>
              <CardDescription>
                Sign-in links last 15 minutes and can only be used once.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full"><Link to="/login">Request a new link</Link></Button>
            </CardContent>
          </>
        ) : (
          <CardContent className="text-muted-foreground flex items-center justify-center gap-3 py-12 text-sm">
            <Loader2 className="size-4 animate-spin" /> Signing you in…
          </CardContent>
        )}
      </Card>
    </div>
  )
}
