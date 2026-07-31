export interface ChannelPref {
  channel_id: string
  channel: string
  type: string
  consent_id: string | null
  status: 'granted' | 'pending' | 'withdrawn' | 'expired' | 'revoked'
  granted: boolean
  granted_at: string | null
  withdrawn_at: string | null
  source: string | null
}

export interface PurposeGroup {
  purpose_id: string
  purpose: string
  slug: string
  description: string | null
  is_mandatory: boolean
  requires_explicit_consent: boolean
  retention_days: number | null
  channels: ChannelPref[]
}

export interface HistoryEntry {
  id: string
  action: string
  created_at: string
  reason: string | null
  actor_type: string
  purpose: string
  channel: string
  source_system: string | null
}

export interface DSARRequest {
  id: string
  request_type: string
  status: string
  description: string | null
  submitted_at: string
  due_date: string
  fulfilled_at: string | null
  denial_reason: string | null
  days_remaining?: number | null
}
