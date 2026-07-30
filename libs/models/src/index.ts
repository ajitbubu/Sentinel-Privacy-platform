/** Shared domain models used by PMP and IDP frontends. */

export type ConsentStatus = 'pending' | 'granted' | 'withdrawn' | 'expired' | 'revoked'
export type LegalBasis = 'consent' | 'legitimate_interest' | 'contract' | 'legal_obligation'
export type DSARType = 'access' | 'deletion' | 'rectification' | 'export' | 'portability'
export type DSARStatus = 'submitted' | 'acknowledged' | 'in_progress' | 'fulfilled' | 'denied' | 'cancelled'

export interface Consent {
  id: string
  subject_id: string
  purpose: string
  channel: string
  legal_basis: LegalBasis
  status: ConsentStatus
  granted_at?: string
  withdrawn_at?: string
  expires_at?: string
  source_system: string
}

export interface Subject {
  id: string
  email: string
  first_name?: string
  last_name?: string
  status: 'active' | 'archived' | 'deleted_pending'
}

export interface DSARRequest {
  id: string
  subject_id: string
  request_type: DSARType
  status: DSARStatus
  submitted_at: string
  due_date: string
  fulfilled_at?: string
}

export interface Banner {
  id: string
  name: string
  slug: string
  title?: string
  message?: string
  status: 'draft' | 'published' | 'scheduled' | 'archived'
  current_version: number
  published_at?: string
}

export interface WebhookConfig {
  id: string
  target_system: 'salesforce' | 'hubspot' | 'outreach' | 'highspot' | 'custom'
  target_url: string
  event_type: string
  is_active: boolean
  last_delivery_status?: 'success' | 'failed' | 'pending'
}
