# DPDP requirements bearing on the data model

India's Digital Personal Data Protection Act 2023 + DPDP Rules 2025
(gazette 13 Nov 2025, commencement G.S.R. 843(E)).

**Key date: 13 November 2026** — the Consent Manager provision (S.6(7)–(9)) commences.

## Terminology

DPDP uses different terms, and they appear in generated legal documents:

| GDPR | DPDP |
|---|---|
| Data Subject | **Data Principal** |
| Data Controller | **Data Fiduciary** |
| Data Processor | Data Processor |

## The nine statutory registers

The compliance pack maintains nine registers. Platform coverage today:

| Register | Platform | Status |
|---|---|---|
| Consent Register | `consents` | Partial — no notice version, language, or mode |
| Grievance Register | — | Absent |
| Breach Register | — | Absent |
| Rights Requests | `dsar_requests` | Partial — wrong right set |
| Vendor Register | — | Absent |
| Deletion Log | — | Absent |
| RoPA | — | Absent |
| Training Log | — | Out of scope (HR) |
| Evidence Register | `audit_log` | Partial |

## Consent Register — the required columns

Straight from the pack. Mode key: `P` physical form, `D` digital,
`T` thumb impression with witness attestation.

    Patient ID | Date & time | Language version | Notice version |
    Purposes consented | Mode (P/D/T) | Withdrawal date

`Language version` matters because S.5(3) and R.3 require the notice to be
available in English and the 22 languages of the Eighth Schedule to the
Constitution, and the register records which one the person actually received.

## Rights (S.11–14)

- **S.11** access to a summary of data and processing
- **S.12** correction, completion, updation, erasure
- **S.13** grievance redressal — *distinct right*, response within 90 days
- **S.14** nomination — name someone to act on death or incapacity

No portability right exists in DPDP.

## Legal bases

Consent under **S.6**, or a "legitimate use" under **S.7**. The closed S.7 list
relevant to clinical establishments includes:

- **S.7(f)** emergency care to protect life or health
- **S.7(g)** treatment during epidemic or threat to public health
- statutory or regulatory reporting required by law

There is no equivalent of GDPR's open-ended legitimate-interest balancing test.

## Other obligations touching the platform

| Obligation | Provision |
|---|---|
| Security safeguards; **logs retained 1 year** | S.8(5); R.6 |
| Breach notification — principals without delay, Board initial + 72h report | S.8(6); R.7 |
| Erasure on withdrawal or purpose completion | S.6(6), S.8(7); R.8 |
| Published contact for queries and grievances | S.8(9)–(10); R.9 |
| Written agreement with every processor | S.8(2) |
| Verifiable guardian consent, under **18** | S.9; R.10–12, Sch. IV |
| Healthcare exemption from guardian consent | S.9(4); R.12, Sch. IV Part A entry 1 |
| Cross-border transfer restrictions | S.16; R.15 |
| Consent Manager — receive and honour consent through one | S.6(7)–(9); R.4 |
| Existing data: fresh notice, continue lawfully | S.5(2) |

## Schema changes this implies

    -- Evidence of what was shown (S.6(10), R.3) — highest priority
    ALTER TABLE consents ADD COLUMN banner_version_id UUID REFERENCES banner_versions(id);
    ALTER TABLE consents ADD COLUMN language_version  VARCHAR(35);
    ALTER TABLE consents ADD COLUMN capture_mode      VARCHAR(30) DEFAULT 'digital';
    ALTER TABLE consents ADD COLUMN witness_name      VARCHAR(255);
    ALTER TABLE consents ADD COLUMN cross_border      BOOLEAN DEFAULT FALSE;

    ALTER TABLE purposes ADD COLUMN jurisdiction VARCHAR(10) DEFAULT 'GDPR';

    -- New tables: nominations, grievances, breach_register,
    --             deletion_log, processing_activities, guardians
