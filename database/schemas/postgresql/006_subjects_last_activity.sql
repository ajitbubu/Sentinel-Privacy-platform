-- auth_service (pmp), identity_service (external-api), and dsar_admin_service
-- (idp) all read/write subjects.last_activity, but the initial schema never
-- added it.
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS last_activity TIMESTAMPTZ;
