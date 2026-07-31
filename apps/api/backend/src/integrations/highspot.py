"""Highspot user email-preference sync."""
from .base import BaseConnector, ConsentSignal, _truthy


class HighspotConnector(BaseConnector):
    system = "highspot"
    signature_header = "x-highspot-signature"

    def parse_inbound(self, payload: dict) -> list[ConsentSignal]:
        email = payload.get("email") or payload.get("user_email")
        if not email:
            return []
        prefs = payload.get("preferences") or {}
        signals = []
        for key, purpose in (("email_updates", "product_updates"), ("marketing", "marketing")):
            if key in prefs:
                signals.append(ConsentSignal(
                    email=email, granted=_truthy(prefs[key]), purpose=purpose,
                    channel="email", source_system=self.system,
                    external_id=str(payload.get("user_id", "")),
                    occurred_at=payload.get("updated_at"),
                ))
        return signals

    def build_outbound(self, event: dict) -> dict | None:
        data = event.get("data", {})
        if event.get("type") != "consent.updated":
            return None
        return {
            "method": "PUT", "path": "/api/v1/users/preferences",
            "body": {"email": data.get("subject_email", ""),
                     "preferences": {"marketing": data.get("status") == "granted"}},
        }
