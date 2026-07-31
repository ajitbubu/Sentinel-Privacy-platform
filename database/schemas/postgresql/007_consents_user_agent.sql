-- pmp-backend consent_service.grant() writes source_ip_address + user_agent
-- together, but the initial schema only added source_ip_address.
ALTER TABLE consents ADD COLUMN IF NOT EXISTS user_agent VARCHAR(500);
