import { api } from './api'

export interface AdminUser {
  id: string
  email: string
  name: string
  role: string
  permissions: string[]
}

const ACCESS = 'idp_access_token'
const REFRESH = 'idp_refresh_token'
const USER = 'idp_user'

export class MfaRequired extends Error {}

export async function login(email: string, password: string, mfaCode?: string): Promise<AdminUser> {
  try {
    const { data } = await api.post('/auth/login', {
      email, password, mfa_code: mfaCode || null,
    })
    sessionStorage.setItem(ACCESS, data.access_token)
    sessionStorage.setItem(REFRESH, data.refresh_token)
    sessionStorage.setItem(USER, JSON.stringify(data.user))
    return data.user
  } catch (err: unknown) {
    const res = (err as { response?: { status?: number; data?: { detail?: unknown } } }).response
    const detail = res?.data?.detail as { code?: string; message?: string } | string | undefined
    if (res?.status === 401 && typeof detail === 'object' && detail?.code === 'MFA_REQUIRED') {
      throw new MfaRequired(detail.message ?? 'MFA code required')
    }
    throw err
  }
}

export async function logout(): Promise<void> {
  const refresh = sessionStorage.getItem(REFRESH)
  if (refresh) {
    try { await api.post('/auth/logout', { refresh_token: refresh }) } catch { /* best effort */ }
  }
  sessionStorage.clear()
}

export async function refreshSession(): Promise<boolean> {
  const refresh = sessionStorage.getItem(REFRESH)
  if (!refresh) return false
  try {
    const { data } = await api.post('/auth/refresh', { refresh_token: refresh })
    sessionStorage.setItem(ACCESS, data.access_token)
    sessionStorage.setItem(REFRESH, data.refresh_token)
    sessionStorage.setItem(USER, JSON.stringify(data.user))
    return true
  } catch {
    sessionStorage.clear()
    return false
  }
}

export function currentUser(): AdminUser | null {
  const raw = sessionStorage.getItem(USER)
  return raw ? (JSON.parse(raw) as AdminUser) : null
}

export function isAuthenticated(): boolean {
  return Boolean(sessionStorage.getItem(ACCESS))
}

export function hasPermission(permission: string): boolean {
  const user = currentUser()
  if (!user) return false
  return user.permissions.includes('*') || user.permissions.includes(permission)
}
