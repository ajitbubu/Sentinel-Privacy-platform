from .base import BaseConnector, ConsentSignal
from .highspot import HighspotConnector
from .hubspot import HubSpotConnector
from .outreach import OutreachConnector
from .salesforce import SalesforceConnector

REGISTRY: dict[str, BaseConnector] = {
    "salesforce": SalesforceConnector(),
    "hubspot": HubSpotConnector(),
    "outreach": OutreachConnector(),
    "highspot": HighspotConnector(),
}


def get_connector(system: str) -> BaseConnector | None:
    return REGISTRY.get(system.lower())


__all__ = ["ConsentSignal", "REGISTRY", "get_connector"]
