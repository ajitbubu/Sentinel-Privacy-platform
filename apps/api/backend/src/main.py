"""External API - third-party consent ingestion + webhook receivers."""
from fastapi import FastAPI

from src.api.v1.routes import consent_external, webhooks, health

app = FastAPI(
    title="Consent External API",
    description="Third-party consent submission + inbound webhooks (Salesforce, HubSpot, Outreach, Highspot)",
    version="1.0.0",
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(consent_external.router, prefix="/api/v1/consent", tags=["consent"])
app.include_router(webhooks.router, prefix="/api/v1/webhook", tags=["webhooks"])
