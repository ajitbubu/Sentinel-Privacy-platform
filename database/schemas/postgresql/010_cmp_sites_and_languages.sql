-- Cookie/consent management platform: customer sites, languages, receipts.
--
-- DPDP-first. The language dimension is not internationalisation — s.5(3)
-- requires the notice in English or an Eighth Schedule language, and the
-- Consent Register records which one was served. Language is evidence.

-- ---------------------------------------------------------------- languages
-- The 22 languages of the Eighth Schedule to the Constitution of India,
-- plus English. Held as data rather than an enum because the Schedule has
-- been amended before (92nd Amendment added four in 2003).
CREATE TABLE IF NOT EXISTS languages (
    code               VARCHAR(10) PRIMARY KEY,
    name_english       VARCHAR(60)  NOT NULL,
    name_native        VARCHAR(120) NOT NULL,
    script             VARCHAR(40),
    is_eighth_schedule BOOLEAN NOT NULL DEFAULT FALSE,
    is_rtl             BOOLEAN NOT NULL DEFAULT FALSE
);

INSERT INTO languages (code, name_english, name_native, script, is_eighth_schedule, is_rtl) VALUES
('en',  'English',   'English',        'Latin',      FALSE, FALSE),
('as',  'Assamese',  'অসমীয়া',          'Bengali',    TRUE,  FALSE),
('bn',  'Bengali',   'বাংলা',            'Bengali',    TRUE,  FALSE),
('brx', 'Bodo',      'बड़ो',             'Devanagari', TRUE,  FALSE),
('doi', 'Dogri',     'डोगरी',            'Devanagari', TRUE,  FALSE),
('gu',  'Gujarati',  'ગુજરાતી',           'Gujarati',   TRUE,  FALSE),
('hi',  'Hindi',     'हिन्दी',             'Devanagari', TRUE,  FALSE),
('kn',  'Kannada',   'ಕನ್ನಡ',            'Kannada',    TRUE,  FALSE),
('ks',  'Kashmiri',  'کٲشُر',            'Perso-Arabic', TRUE, TRUE),
('kok', 'Konkani',   'कोंकणी',           'Devanagari', TRUE,  FALSE),
('mai', 'Maithili',  'मैथिली',            'Devanagari', TRUE,  FALSE),
('ml',  'Malayalam', 'മലയാളം',         'Malayalam',  TRUE,  FALSE),
('mni', 'Manipuri',  'ꯃꯤꯇꯩ ꯂꯣꯟ',        'Meitei Mayek', TRUE, FALSE),
('mr',  'Marathi',   'मराठी',            'Devanagari', TRUE,  FALSE),
('ne',  'Nepali',    'नेपाली',            'Devanagari', TRUE,  FALSE),
('or',  'Odia',      'ଓଡ଼ିଆ',            'Odia',       TRUE,  FALSE),
('pa',  'Punjabi',   'ਪੰਜਾਬੀ',            'Gurmukhi',   TRUE,  FALSE),
('sa',  'Sanskrit',  'संस्कृतम्',          'Devanagari', TRUE,  FALSE),
('sat', 'Santali',   'ᱥᱟᱱᱛᱟᱲᱤ',         'Ol Chiki',   TRUE,  FALSE),
('sd',  'Sindhi',    'سنڌي',            'Perso-Arabic', TRUE, TRUE),
('ta',  'Tamil',     'தமிழ்',            'Tamil',      TRUE,  FALSE),
('te',  'Telugu',    'తెలుగు',            'Telugu',     TRUE,  FALSE),
('ur',  'Urdu',      'اردو',             'Perso-Arabic', TRUE, TRUE)
ON CONFLICT (code) DO NOTHING;

COMMENT ON TABLE languages IS
  'Eighth Schedule languages (DPDP s.5(3), R.3). is_rtl drives banner layout '
  'direction — Kashmiri, Sindhi and Urdu are written right-to-left.';

-- ------------------------------------------------------------------- sites
CREATE TABLE IF NOT EXISTS sites (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,

    -- Publishable key. PUBLIC BY DESIGN — it ships in the customer's page
    -- source. It can only read public config and write consent for its own
    -- pseudonymous bearer; it can never read another visitor's consent.
    -- Stored in clear precisely because it is not a secret; the security
    -- control is the origin allowlist below.
    publishable_key VARCHAR(64) NOT NULL UNIQUE,
    allowed_origins TEXT[] NOT NULL DEFAULT '{}',

    -- Data Fiduciary identity. DPDP s.6(3) and s.8(9) with R.9 require the
    -- notice to name the Data Fiduciary and the person who answers queries.
    -- NOT NULL because a notice without them is not a valid notice.
    data_fiduciary_name     VARCHAR(255) NOT NULL,
    data_fiduciary_address  TEXT,
    grievance_officer_name  VARCHAR(255),
    grievance_officer_email VARCHAR(255),
    grievance_officer_phone VARCHAR(50),

    -- Languages offered. default_language must appear in available_languages.
    default_language    VARCHAR(10) NOT NULL DEFAULT 'en' REFERENCES languages(code),
    available_languages VARCHAR(10)[] NOT NULL DEFAULT ARRAY['en'],

    banner_id  UUID REFERENCES banners(id),
    auto_block BOOLEAN NOT NULL DEFAULT TRUE,
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,

    created_by_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT default_language_is_available
      CHECK (default_language = ANY(available_languages))
);

CREATE INDEX IF NOT EXISTS idx_sites_key    ON sites(publishable_key) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_sites_active ON sites(is_active) WHERE is_active = TRUE;

-- ------------------------------------------------------ banner translations
CREATE TABLE IF NOT EXISTS banner_translations (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    banner_id UUID NOT NULL REFERENCES banners(id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL REFERENCES languages(code),

    title                 VARCHAR(255),
    message               TEXT,
    button_accept_text    VARCHAR(100),
    button_reject_text    VARCHAR(100),
    button_customize_text VARCHAR(100),
    withdraw_text         VARCHAR(100),

    -- Flagged, not hidden. A machine translation of a legal notice is a
    -- liability the DPO should be able to see and review, not something the
    -- system quietly presents as equivalent to a reviewed one.
    is_machine_translated BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_by_user_id   UUID,
    reviewed_at           TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_banner_language UNIQUE (banner_id, language_code)
);

CREATE INDEX IF NOT EXISTS idx_translations_banner ON banner_translations(banner_id);

-- --------------------------------------------------------- consent receipts
-- An anonymous visitor is not a `subject` — subjects.email is NOT NULL, and
-- inventing a placeholder email to force one would be a lie in the data.
-- Cookie consent therefore lives here against a pseudonymous id, and is
-- promoted into `consents` only when identify() supplies a real identity.
CREATE TABLE IF NOT EXISTS consent_receipts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id VARCHAR(40) NOT NULL UNIQUE,

    site_id         UUID NOT NULL REFERENCES sites(id),
    pseudonymous_id UUID NOT NULL,
    subject_id      UUID REFERENCES subjects(id),   -- set on identify()

    -- Evidence. Same shape as consents (migration 009) so the two are
    -- comparable and the DSAR export can render them together.
    banner_version_id UUID REFERENCES banner_versions(id),
    language_version  VARCHAR(10) REFERENCES languages(code),
    purposes          JSONB NOT NULL DEFAULT '{}',
    purposes_presented JSONB NOT NULL DEFAULT '{}',
    interaction_type  VARCHAR(30) NOT NULL,

    -- Jurisdiction evidence without storing a full identifier: /24 for IPv4,
    -- /48 for IPv6. Enough to show where consent was given, not enough to
    -- single someone out.
    ip_truncated     INET,
    user_agent_hash  VARCHAR(64),
    page_url         TEXT,

    signature   TEXT NOT NULL,
    collected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMP WITH TIME ZONE,

    CONSTRAINT valid_interaction CHECK (interaction_type IN
      ('accept_all', 'reject_all', 'save_preferences', 'close', 'withdraw'))
);

CREATE INDEX IF NOT EXISTS idx_receipts_pseudo  ON consent_receipts(pseudonymous_id);
CREATE INDEX IF NOT EXISTS idx_receipts_site    ON consent_receipts(site_id, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_subject ON consent_receipts(subject_id) WHERE subject_id IS NOT NULL;

COMMENT ON COLUMN consent_receipts.purposes_presented IS
  'What was on screen, not merely what was chosen. Proving valid consent under '
  's.6(10) requires showing the options offered, not just the outcome.';

-- Identity linking: one subject may have several pseudonymous ids across
-- devices and browsers.
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS pseudonymous_ids UUID[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_subjects_pseudo ON subjects USING GIN (pseudonymous_ids);
