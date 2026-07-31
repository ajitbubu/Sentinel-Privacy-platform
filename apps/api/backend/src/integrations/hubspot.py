"""HubSpot contact property sync."""
from .base import BaseConnector, ConsentSignal, _truthy

PROPERTY_MAP = {
    "email_opt_in": ("marketing", "email"),
    "hs_email_optout": ("marketing", "email"),          # inverted
    "email_open_opt_out": ("marketing", "email"),       # inverted
    "sms_opt_in": ("marketing", "sms"),
    "analytics_consent": ("analytics", "web"),
}
INVERTED = {"hs_email_optout", "email_open_opt_out"}


class HubSpotConnector(BaseConnector):
    system = "hubspot"
    signature_header = "x-hubspot-signature-v3"

    def parse_inbound(self, payload: dict) -> list[ConsentSignal]:
        email = payload.get("email") or (payload.get("properties", {}).get("email", {}) or {}).get("value")
        if not email:
            return []

        props = payload.get("properties") or {}
        external_id = str(payload.get("objectId") or payload.get("object_id") or "")
        occurred = payload.get("occurredAt") or payload.get("timestamp")

        signals = []
        for prop, value in props.items():
            mapping = PROPERTY_MAP.get(prop)
            if mapping is None:
                continue
            purpose, channel = mapping
            # HubSpot nests values: {"value": "true", "timestamp": ...}
            raw = value.get("value") if isinstance(value, dict) else value
            granted = _truthy(raw)
            if prop in INVERTED:
                granted = not granted
            signals.append(ConsentSignal(
                email=email, granted=granted, purpose=purpose, channel=channel,
                source_system=self.system, external_id=external_id,
                occurred_at=str(occurred) if occurred else None,
                metadata={"property": prop},
            ))
        return signals

    def build_outbound(self, event: dict) -> dict | None:
        data = event.get("data", {})
        if event.get("type") != "consent.updated":
            return None
        granted = data.get("status") == "granted"
        return {
            "method": "POST",
            "path": "/crm/v3/objects/contacts/batch/update",
            "body": {"inputs": [{
                "idProperty": "email",
                "id": data.get("subject_email", ""),
                "properties": {
                    "email_opt_in": str(granted).lower(),
                    "hs_email_optout": str(not granted).lower(),
                },
            }]},
        }
