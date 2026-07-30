-- API keys for external clients (Salesforce, HubSpot, custom apps).
-- Only the SHA-256 hash is stored; the plaintext key is shown once at creation.

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name            VARCHAR(255) NOT NULL,
    client_system   VARCHAR(50)  NOT NULL,   -- salesforce, hubspot, outreach, highspot, custom
    key_hash        VARCHAR(64)  NOT NULL UNIQUE,
    key_prefix      VARCHAR(12)  NOT NULL,   -- first chars, shown in UI so keys are identifiable

    -- Authorization
    tier            VARCHAR(20)  NOT NULL DEFAULT 'standard',  -- standard | premium | enterprise
    scopes          TEXT[]       NOT NULL DEFAULT ARRAY['consent:write'],
    allowed_ips     INET[]       DEFAULT '{}',                 -- empty = any IP

    -- Lifecycle
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    expires_at      TIMESTAMP WITH TIME ZONE,
    last_used_at    TIMESTAMP WITH TIME ZONE,
    revoked_at      TIMESTAMP WITH TIME ZONE,
    revoked_reason  TEXT,

    -- Audit
    created_by_user_id UUID,
    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_tier CHECK (tier IN ('standard', 'premium', 'enterprise'))
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash   ON api_keys(key_hash) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_api_keys_system ON api_keys(client_system);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
