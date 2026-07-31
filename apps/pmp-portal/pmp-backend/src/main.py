"""PMP Portal Backend — customer-facing consent API."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.routes import auth, consent, dsar, events, health, preference
from src.config.settings import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="PMP Portal API",
    description="Customer-facing consent management: preferences, consent, DSAR",
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
app.include_router(consent.router, prefix="/api/v1/consent", tags=["consent"])
app.include_router(preference.router, prefix="/api/v1/preference-center", tags=["preferences"])
app.include_router(dsar.router, prefix="/api/v1/dsar", tags=["dsar"])
app.include_router(events.router, tags=["events"])
