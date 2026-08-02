"""External API - third-party consent ingestion + webhook receivers."""
from fastapi import FastAPI

from src.api.v1.routes import cmp, consent_external, webhooks, health
from src.api.v1.routes.cmp import wellknown_router

app = FastAPI(
    title="Consent External API",
    description="Third-party consent submission + inbound webhooks (Salesforce, HubSpot, Outreach, Highspot)",
    version="1.0.0",
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(consent_external.router, prefix="/api/v1/consent", tags=["consent"])
app.include_router(webhooks.router, prefix="/api/v1/webhook", tags=["webhooks"])
# Public CMP surface. Separate prefix because it is a different trust boundary
# from the rest of the API: authenticated by a publishable key plus the browser
# Origin header, not a secret API key. Keeping it on its own path makes it
# straightforward to give it different WAF and rate-limit rules at the edge.
app.include_router(cmp.router, prefix="/api/v1/cmp", tags=["cmp"])

# RFC 8615 puts well-known URIs at the origin root, not under an API prefix.
# JWKS consumers derive this path from the issuer origin, so a receipt verifier
# pointed at https://api.example.com will look here and nowhere else.
app.include_router(wellknown_router, tags=["cmp"])
