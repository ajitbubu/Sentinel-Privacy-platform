-- Consent evidence: what was actually shown, in which language, captured how.
--
-- DPDP s.6(10) places the burden of proving valid consent on the Data Fiduciary,
-- and Rule 3 requires the notice version to be recorded. GDPR Art. 7(1) imposes
-- the same shape of burden ("demonstrate that the data subject has consented").
-- banner_versions already holds immutable snapshots of exactly what was displayed;
-- until now nothing joined a consent record to one, so the evidence and the
-- consent could not be tied together.

ALTER TABLE consents ADD COLUMN IF NOT EXISTS banner_version_id UUID REFERENCES banner_versions(id);
ALTER TABLE consents ADD COLUMN IF NOT EXISTS language_version  VARCHAR(35);
ALTER TABLE consents ADD COLUMN IF NOT EXISTS capture_mode      VARCHAR(30) NOT NULL DEFAULT 'digital';
ALTER TABLE consents ADD COLUMN IF NOT EXISTS witness_name      VARCHAR(255);
ALTER TABLE consents ADD COLUMN IF NOT EXISTS cross_border      BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN consents.banner_version_id IS
  'Immutable snapshot of the notice displayed. DPDP s.6(10) / R.3; GDPR Art. 7(1).';
COMMENT ON COLUMN consents.language_version IS
  'Language the notice was served in. DPDP s.5(3) requires English plus the 22 '
  'languages of the Eighth Schedule; the Consent Register records which was received.';
COMMENT ON COLUMN consents.capture_mode IS
  'digital | physical | thumb_impression_witnessed. The Consent Register mode key '
  'is P/D/T; thumb impression with witness attestation is a recognised mode in '
  'Indian healthcare and needs a representable form.';
COMMENT ON COLUMN consents.cross_border IS 'Purpose involves transfer outside India. DPDP s.16, R.15.';

ALTER TABLE consents DROP CONSTRAINT IF EXISTS valid_capture_mode;
ALTER TABLE consents ADD CONSTRAINT valid_capture_mode
  CHECK (capture_mode IN ('digital', 'physical', 'thumb_impression_witnessed'));

-- A thumb impression is only evidence if the attesting witness is named.
-- Enforced at the database as well as the service: the UI is not a security
-- boundary, and neither is a single application layer.
ALTER TABLE consents DROP CONSTRAINT IF EXISTS witness_required_for_thumb_impression;
ALTER TABLE consents ADD CONSTRAINT witness_required_for_thumb_impression
  CHECK (capture_mode <> 'thumb_impression_witnessed'
         OR (witness_name IS NOT NULL AND length(trim(witness_name)) > 0));

CREATE INDEX IF NOT EXISTS idx_consents_banner_version ON consents(banner_version_id);

-- Consent rows written before this migration have no recorded notice version.
-- That is a fact about the data, not a gap to paper over: leaving them NULL is
-- what lets a compliance report distinguish "captured with evidence" from
-- "captured before evidence was recorded".
