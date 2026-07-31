-- audit_service.log_audit() writes changed_fields + legal_basis on every entry;
-- the initial schema never added them.
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS changed_fields TEXT[] DEFAULT '{}';
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS legal_basis VARCHAR(100);
