"""Consent conflict-resolution rules.

Deliberately dependency-free (stdlib only) so the rules can be unit-tested
without a database, Redis, or any service wiring. This is the most
consequential logic in the system — it decides whose signal wins when two
systems disagree about whether someone consented — so it must be trivially
testable and reviewable in isolation.

THE RULE
--------
Naive "opt-out always wins" permanently breaks re-subscription: a person who
withdraws could never opt back in, because their new grant would always lose
to the older withdrawal. What we actually want:

  1. Inside the conflict window (default 24h), a withdrawal beats a grant
     regardless of timestamp — this stops a lagging CRM sync from resurrecting
     consent someone just withdrew.
  2. Outside the window, source tier decides: a first-party explicit action
     (PMP portal, cookie banner, DPO console) beats a third-party sync.
  3. Among same-tier signals, the newest wins.

Withdrawals are always honoured regardless of source tier: the safe direction
wins. A third-party system may not be trusted to grant consent on someone's
behalf, but it is always trusted to report that they opted out.
"""
from datetime import datetime, timedelta, timezone

CONFLICT_WINDOW_HOURS = 24

# Consent Register mode key: P physical, D digital,
# T thumb impression with witness attestation.
CAPTURE_MODES = {"digital", "physical", "thumb_impression_witnessed"}


class EvidenceError(Exception):
    """Evidence rule violation. Message is safe to surface to the caller."""


def validate_evidence(capture_mode: str, witness_name: str | None) -> None:
    """A thumb impression is only evidence if the attesting witness is named.

    Pure, so it can be tested without a database. Also enforced by a CHECK
    constraint on `consents` — the UI is not a security boundary and neither
    is any single application layer; this is the one that produces a usable
    error message.
    """
    if capture_mode not in CAPTURE_MODES:
        raise EvidenceError(f"capture_mode must be one of {sorted(CAPTURE_MODES)}")
    if capture_mode == "thumb_impression_witnessed" and not (witness_name or "").strip():
        raise EvidenceError(
            "A witness name is required when consent is captured by thumb impression."
        )

# Higher tier wins outside the conflict window.
SOURCE_TIER = {
    "PMP": 3, "pmp_portal": 3, "cookie_banner": 3, "IDP": 3,      # first-party explicit
    "API": 2,                                                      # direct API
    "salesforce": 1, "hubspot": 1, "outreach": 1, "highspot": 1,   # third-party sync
}
DEFAULT_TIER = 1


def tier(source: str) -> int:
    return SOURCE_TIER.get(source, SOURCE_TIER.get((source or "").lower(), DEFAULT_TIER))


def _aware(dt: datetime | None) -> datetime | None:
    """Some drivers return naive datetimes; treat those as UTC rather than crash."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def should_apply(existing: dict | None, new_status: str, new_source: str,
                 now: datetime | None = None) -> tuple[bool, str]:
    """Decide whether an incoming signal supersedes the existing consent.

    Returns (apply, reason). Pure — no I/O, no globals, no clock unless injected.
    """
    if existing is None:
        return True, "no prior consent"

    now = now or datetime.now(timezone.utc)
    if existing["status"] == new_status:
        return False, "no change"

    # Rule 1 — protect a fresh withdrawal from stale grants.
    withdrawn_at = _aware(existing.get("withdrawn_at"))
    if existing["status"] == "withdrawn" and new_status == "granted" and withdrawn_at:
        if now - withdrawn_at < timedelta(hours=CONFLICT_WINDOW_HOURS):
            if tier(new_source) < 3:
                return False, (
                    f"withdrawal within {CONFLICT_WINDOW_HOURS}h conflict window "
                    f"outranks grant from '{new_source}'"
                )
            return True, "first-party explicit re-grant inside window"

    # Withdrawals always apply — the safe direction wins regardless of tier.
    if new_status == "withdrawn":
        return True, "withdrawal always honoured"

    # Rule 2 — tier precedence outside the window.
    existing_tier = tier(existing.get("source_system", ""))
    if tier(new_source) < existing_tier:
        return False, f"source '{new_source}' outranked by existing '{existing.get('source_system')}'"

    # Rule 3 — same or higher tier: newest wins, and we are newest by construction.
    return True, "supersedes prior consent"
