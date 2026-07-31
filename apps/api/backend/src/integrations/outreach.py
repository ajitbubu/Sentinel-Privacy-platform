"""Outreach prospect opt-out sync."""
from .base import BaseConnector, ConsentSignal, _truthy


class OutreachConnector(BaseConnector):
    system = "outreach"
    signature_header = "outreach-webhook-signature"

    def parse_inbound(self, payload: dict) -> list[ConsentSignal]:
        data = payload.get("data", payload)
        attrs = data.get("attributes", data)
        email = attrs.get("emails", [None])[0] if isinstance(attrs.get("emails"), list) \
            else attrs.get("email")
        if not email:
            return []
        opted_out = _truthy(attrs.get("optedOut") or attrs.get("opted_out"))
        return [ConsentSignal(
            email=email, granted=not opted_out, purpose="marketing", channel="email",
            source_system=self.system, external_id=str(data.get("id", "")),
            occurred_at=attrs.get("updatedAt"),
        )]

    def build_outbound(self, event: dict) -> dict | None:
        data = event.get("data", {})
        if event.get("type") != "consent.updated":
            return None
        return {
            "method": "PATCH", "path": "/api/v2/prospects",
            "body": {"data": {"type": "prospect", "attributes": {
                "optedOut": data.get("status") != "granted",
            }}},
        }
