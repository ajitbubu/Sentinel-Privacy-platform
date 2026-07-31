"""Salesforce Contact/Lead consent sync."""
from .base import BaseConnector, ConsentSignal, _truthy

# Salesforce custom field -> (purpose, channel)
FIELD_MAP = {
    "Email_Opt_In__c": ("marketing", "email"),
    "Marketing_Consent__c": ("marketing", "email"),
    "SMS_Opt_In__c": ("marketing", "sms"),
    "Analytics_Consent__c": ("analytics", "web"),
    "HasOptedOutOfEmail": ("marketing", "email"),  # standard field, inverted
}
INVERTED = {"HasOptedOutOfEmail"}


class SalesforceConnector(BaseConnector):
    system = "salesforce"
    signature_header = "x-salesforce-signature"

    def parse_inbound(self, payload: dict) -> list[ConsentSignal]:
        email = payload.get("email") or payload.get("Email")
        if not email:
            return []

        changed = payload.get("fields_changed") or payload.get("fields") or {}
        occurred = payload.get("timestamp") or payload.get("LastModifiedDate")
        external_id = payload.get("contact_id") or payload.get("Id")

        signals = []
        for field_name, raw in changed.items():
            mapping = FIELD_MAP.get(field_name)
            if mapping is None:
                continue
            purpose, channel = mapping
            granted = _truthy(raw)
            if field_name in INVERTED:
                granted = not granted   # HasOptedOutOfEmail=true means NOT granted
            signals.append(ConsentSignal(
                email=email, granted=granted, purpose=purpose, channel=channel,
                source_system=self.system, external_id=external_id,
                occurred_at=occurred, metadata={"field": field_name},
            ))
        return signals

    def build_outbound(self, event: dict) -> dict | None:
        data = event.get("data", {})
        if event.get("type") != "consent.updated":
            return None
        granted = data.get("status") == "granted"
        return {
            "method": "PATCH",
            "path": "/services/data/v59.0/sobjects/Contact/Email/"
                    f"{data.get('subject_email', '')}",
            "body": {
                "Email_Opt_In__c": granted,
                "HasOptedOutOfEmail": not granted,
                "Consent_Last_Updated__c": event.get("timestamp"),
            },
        }
