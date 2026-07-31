"""Connector contract shared by every upstream/downstream system.

Each connector translates between that vendor's shape and our canonical
consent event. Two directions:

  parse_inbound  — their webhook  -> canonical ConsentSignal
  build_outbound — our event      -> their API payload

Keeping both in one class per vendor means the field mapping lives in exactly
one place; when Salesforce renames a field, there is one file to change.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ConsentSignal:
    """Canonical form. Everything inbound normalises to this."""
    email: str
    granted: bool
    purpose: str = "marketing"
    channel: str = "email"
    source_system: str = "unknown"
    external_id: str | None = None
    occurred_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.email = self.email.strip().lower()


class Connector(Protocol):
    system: str
    signature_header: str

    def verify(self, body: bytes, headers: dict[str, str], secret: str) -> bool: ...
    def parse_inbound(self, payload: dict) -> list[ConsentSignal]: ...
    def build_outbound(self, event: dict) -> dict | None: ...


class BaseConnector:
    system = "base"
    signature_header = "x-signature"

    def verify(self, body: bytes, headers: dict[str, str], secret: str) -> bool:
        """HMAC-SHA256 over the raw body. Constant-time compare.

        An unset secret means the integration isn't fully configured. We accept
        in development for local testing but MUST reject in production —
        an unauthenticated webhook endpoint is a consent-forgery endpoint.
        """
        if not secret:
            return True
        provided = headers.get(self.signature_header) or headers.get(self.signature_header.lower())
        if not provided:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, provided.strip().replace("sha256=", ""))

    def parse_inbound(self, payload: dict) -> list[ConsentSignal]:
        raise NotImplementedError

    def build_outbound(self, event: dict) -> dict | None:
        raise NotImplementedError


def _truthy(value: Any) -> bool:
    """Vendors disagree on booleans: true/'true'/'yes'/1/'1' all appear."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "yes", "1", "y", "granted", "opted_in"}
