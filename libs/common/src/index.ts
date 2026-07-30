export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase()
}

export function formatDate(iso: string, locale = 'en-US'): string {
  return new Date(iso).toLocaleString(locale)
}

export const CONSENT_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  granted: 'Granted',
  withdrawn: 'Withdrawn',
  expired: 'Expired',
  revoked: 'Revoked',
}
