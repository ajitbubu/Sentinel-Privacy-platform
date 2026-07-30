import { api } from './api'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export async function requestMagicLink(email: string): Promise<void> {
  await api.post('/auth/magic-link', { email })
}

export async function verifyMagicLink(token: string): Promise<void> {
  const { data } = await api.post('/auth/verify', { token })
  sessionStorage.setItem(ACCESS_KEY, data.access_token)
  sessionStorage.setItem(REFRESH_KEY, data.refresh_token)
}

export async function refreshSession(): Promise<boolean> {
  const refresh = sessionStorage.getItem(REFRESH_KEY)
  if (!refresh) return false
  try {
    const { data } = await api.post('/auth/refresh', { refresh_token: refresh })
    sessionStorage.setItem(ACCESS_KEY, data.access_token)
    sessionStorage.setItem(REFRESH_KEY, data.refresh_token)
    return true
  } catch {
    logoutLocal()
    return false
  }
}

export async function logout(): Promise<void> {
  const refresh = sessionStorage.getItem(REFRESH_KEY)
  if (refresh) {
    try { await api.post('/auth/logout', { refresh_token: refresh }) } catch { /* best effort */ }
  }
  logoutLocal()
}

export function logoutLocal(): void {
  sessionStorage.removeItem(ACCESS_KEY)
  sessionStorage.removeItem(REFRESH_KEY)
}

export function isAuthenticated(): boolean {
  return Boolean(sessionStorage.getItem(ACCESS_KEY))
}
