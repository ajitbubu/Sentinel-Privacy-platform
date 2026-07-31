export interface Banner {
  id: string; name: string; slug: string; type: 'consent' | 'cookie'
  status: 'draft' | 'published' | 'scheduled' | 'archived'
  description?: string | null; title?: string | null; message?: string | null
  button_accept_text?: string; button_reject_text?: string; button_customize_text?: string
  position: 'bottom' | 'top' | 'modal' | 'sidebar'
  background_color: string; text_color: string; button_color: string
  purposes: string[]; channels: string[]
  current_version: number; published_at?: string | null; updated_at: string
  created_by?: string | null
}
export interface BannerVersion {
  id: string; version: number; change_description: string | null
  created_at: string; is_current: boolean; materially_changed: boolean
  changed_by: string | null
}
export interface DSARQueueItem {
  id: string; request_type: string; status: string; description: string | null
  submitted_at: string; due_date: string; fulfilled_at: string | null
  denial_reason: string | null; subject_email: string; subject_id: string
  days_remaining: number; is_overdue: boolean
}
export interface AuditEntry {
  id: string; entity_type: string; entity_id: string; action: string
  actor_type: string; actor_id: string | null; actor_email: string | null
  reason: string | null; legal_basis: string | null; created_at: string
  changed_fields: string[]
}
export interface Overview {
  active_consents: number; withdrawn_consents: number; total_subjects: number
  open_dsar: number; dsar_due_soon: number; dsar_overdue: number
  consents_7d: number; opt_out_rate: number
}
