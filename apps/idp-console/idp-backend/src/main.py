"""IDP Console Backend - Admin/DPO API (Intranet only)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.routes import (auth, banner, consent_admin, dsar_admin, audit,
                               webhook, api_keys, health)
from src.config.settings import settings

app = FastAPI(
    title="IDP Console API",
    description="Admin/DPO console: banners, consent admin, DSAR, audit, webhooks",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(banner.router, prefix="/api/v1/banner", tags=["banner"])
app.include_router(consent_admin.router, prefix="/api/v1/admin/consent", tags=["consent-admin"])
app.include_router(dsar_admin.router, prefix="/api/v1/admin/dsar", tags=["dsar-admin"])
app.include_router(audit.router, prefix="/api/v1/admin/audit", tags=["audit"])
app.include_router(webhook.router, prefix="/api/v1/admin/webhook", tags=["webhook"])
app.include_router(api_keys.router, prefix="/api/v1/admin/api-keys", tags=["api-keys"])
