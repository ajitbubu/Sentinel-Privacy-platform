-- Banner type (consent vs cookie) and re-consent control.
ALTER TABLE banners        ADD COLUMN IF NOT EXISTS type VARCHAR(20) NOT NULL DEFAULT 'consent';
ALTER TABLE banner_versions ADD COLUMN IF NOT EXISTS materially_changed BOOLEAN NOT NULL DEFAULT FALSE;

-- materially_changed drives re-consent: cosmetic edits must not re-prompt
-- millions of users; adding a purpose must.
COMMENT ON COLUMN banner_versions.materially_changed IS
  'Set by the author, not inferred from a diff. TRUE forces re-consent.';

CREATE INDEX IF NOT EXISTS idx_banners_type_active ON banners(type, is_active) WHERE is_active = TRUE;
