# Regulatory scope

The platform was designed against **GDPR** and **CCPA**. A DPDP (India) compliance
pack has since been reviewed and it changes the picture materially — DPDP is not
GDPR with different labels.

## Read before touching the consent schema

`dpdp-requirements.md` in this directory lists the DPDP obligations that bear on
the data model. The short version:

1. **S.6(10) puts the burden of proving valid consent on the Data Fiduciary.**
   A consent row must therefore record *which notice version, in which language,
   captured by which mode* was actually shown. `banner_versions` holds the
   immutable snapshots; `consents` does not yet reference them. That join is the
   difference between defensible and indefensible.
2. **`legal_basis` currently encodes GDPR.** `legitimate_interest` does not exist
   in DPDP; S.7 has a closed list of "legitimate uses" instead.
3. **DPDP has rights GDPR does not** — nomination (S.14) — and lacks one GDPR has
   (portability). Offering portability in an Indian deployment promises something
   the statute does not require.

Source pack (not in this repo — it is the customer's compliance documentation):
`Sentinel Doc/DPDP Consent Compliance Pack`, 25 documents plus a 9-register workbook.

Full gap analysis with sizing lives in the Claude project as `DPDP-Gap-Analysis.md`.
