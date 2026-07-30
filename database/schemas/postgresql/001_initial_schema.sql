-- Sentinel Privacy Platform - Core Schema
-- Shared by PMP Portal, IDP Console, and External API

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============ SUBJECTS (identities) ============
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    email_normalized VARCHAR(255) NOT NULL,
    email_hash VARCHAR(64) NOT NULL,
    salesforce_id VARCHAR(255),
    hubspot_id VARCHAR(255),
    outreach_id VARCHAR(255),
    highspot_id VARCHAR(255),
    external_id VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    encrypted_phone TEXT,
    country_code VARCHAR(2),
    language VARCHAR(5),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_consent_update TIMESTAMPTZ,
    created_by_system VARCHAR(50),
    deleted_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_subjects_email ON subjects(email_normalized) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_subjects_email_hash ON subjects(email_hash);
CREATE INDEX IF NOT EXISTS idx_subjects_salesforce ON subjects(salesforce_id) WHERE salesforce_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subjects_hubspot ON subjects(hubspot_id) WHERE hubspot_id IS NOT NULL;

-- ============ PURPOSES ============
CREATE TABLE IF NOT EXISTS purposes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    legal_basis_allowed TEXT[] NOT NULL DEFAULT ARRAY['consent'],
    is_mandatory BOOLEAN DEFAULT FALSE,
    requires_explicit_consent BOOLEAN DEFAULT TRUE,
    retention_period_days INT DEFAULT 365,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============ CHANNELS ============
CREATE TABLE IF NOT EXISTS channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    requires_opt_in BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============ CONSENTS ============
CREATE TABLE IF NOT EXISTS consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    purpose_id UUID NOT NULL REFERENCES purposes(id),
    channel_id UUID NOT NULL REFERENCES channels(id),
    legal_basis VARCHAR(50) NOT NULL DEFAULT 'consent',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_at TIMESTAMPTZ,
    withdrawn_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    source_system VARCHAR(50) NOT NULL,
    source_url VARCHAR(500),
    source_ip_address INET,
    created_by_system VARCHAR(50),
    updated_by_user_id UUID,
    metadata JSONB DEFAULT '{}',
    deleted_at TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (status IN ('pending','granted','withdrawn','expired','revoked'))
);

CREATE INDEX IF NOT EXISTS idx_consents_subject ON consents(subject_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_consents_status ON consents(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_consents_source ON consents(source_system);
CREATE INDEX IF NOT EXISTS idx_consents_lookup ON consents(subject_id, purpose_id, channel_id) WHERE deleted_at IS NULL;

-- ============ AUDIT LOG (append-only) ============
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,
    actor_id VARCHAR(255),
    actor_ip_address INET,
    old_values JSONB DEFAULT '{}',
    new_values JSONB DEFAULT '{}',
    reason TEXT,
    is_gdpr_relevant BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE RULE audit_log_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);

-- ============ DSAR REQUESTS ============
CREATE TABLE IF NOT EXISTS dsar_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id UUID NOT NULL REFERENCES subjects(id),
    request_type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'submitted',
    denial_reason TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    due_date TIMESTAMPTZ NOT NULL,
    fulfilled_at TIMESTAMPTZ,
    response_method VARCHAR(50),
    response_download_token VARCHAR(255),
    response_download_expires_at TIMESTAMPTZ,
    created_by_system VARCHAR(50),
    assigned_to_user_id UUID,
    processed_by_user_id UUID,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT valid_dsar_status CHECK (status IN ('submitted','acknowledged','in_progress','fulfilled','denied','cancelled')),
    CONSTRAINT valid_dsar_type CHECK (request_type IN ('access','deletion','rectification','export','portability'))
);

CREATE INDEX IF NOT EXISTS idx_dsar_subject ON dsar_requests(subject_id);
CREATE INDEX IF NOT EXISTS idx_dsar_status ON dsar_requests(status);
CREATE INDEX IF NOT EXISTS idx_dsar_due ON dsar_requests(due_date) WHERE status NOT IN ('fulfilled','denied','cancelled');

-- ============ BANNERS ============
CREATE TABLE IF NOT EXISTS banners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    title VARCHAR(255),
    message TEXT,
    button_accept_text VARCHAR(100),
    button_reject_text VARCHAR(100),
    button_customize_text VARCHAR(100),
    position VARCHAR(50) DEFAULT 'bottom',
    background_color VARCHAR(7),
    text_color VARCHAR(7),
    button_color VARCHAR(7),
    show_on_all_pages BOOLEAN DEFAULT TRUE,
    target_countries VARCHAR(2)[] DEFAULT '{}',
    target_languages VARCHAR(5)[] DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft',
    is_active BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    scheduled_publish_at TIMESTAMPTZ,
    created_by_user_id UUID NOT NULL,
    updated_by_user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_version INT DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT valid_banner_status CHECK (status IN ('draft','published','scheduled','archived'))
);

-- ============ BANNER VERSIONS ============
CREATE TABLE IF NOT EXISTS banner_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banner_id UUID NOT NULL REFERENCES banners(id),
    version INT NOT NULL,
    snapshot JSONB NOT NULL,
    change_description TEXT,
    changed_by_user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_current BOOLEAN DEFAULT FALSE,
    CONSTRAINT unique_banner_version UNIQUE (banner_id, version)
);

-- ============ WEBHOOKS ============
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_system VARCHAR(50) NOT NULL,
    target_url VARCHAR(500) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    auth_type VARCHAR(50) NOT NULL DEFAULT 'api_key',
    api_key TEXT,
    oauth_token TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    retry_strategy VARCHAR(50) DEFAULT 'exponential',
    max_retries INT DEFAULT 10,
    timeout_seconds INT DEFAULT 30,
    headers JSONB DEFAULT '{}',
    last_delivery_at TIMESTAMPTZ,
    last_delivery_status VARCHAR(50),
    consecutive_failures INT DEFAULT 0,
    created_by_user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============ WEBHOOK DELIVERIES ============
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id),
    event_id UUID,
    event_type VARCHAR(100) NOT NULL,
    request_payload JSONB NOT NULL,
    response_status_code INT,
    response_body TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    attempt_number INT DEFAULT 1,
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    next_retry_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_wh_deliveries_webhook ON webhook_deliveries(webhook_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wh_deliveries_retry ON webhook_deliveries(next_retry_at) WHERE status = 'retrying';

-- ============ ADMIN USERS ============
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    permissions TEXT[] DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'invited',
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id UUID,
    CONSTRAINT valid_role CHECK (role IN ('admin','dpo','auditor','analyst'))
);
