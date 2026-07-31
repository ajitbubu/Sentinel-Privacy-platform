"""Inbound webhook receivers for upstream systems."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.services import webhook_ingest
from src.services.webhook_ingest import WebhookError

router = APIRouter()
log = logging.getLogger(__name__)

SUPPORTED = {"salesforce", "hubspot", "outreach", "highspot"}


def _secret_for(system: str) -> str:
    return getattr(settings, f"{system}_webhook_secret", "") or ""


async def _handle(system: str, request: Request, db: Session) -> dict:
    if system not in SUPPORTED:
        raise HTTPException(404, f"Unknown system '{system}'")

    raw = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Body must be JSON")

    secret = _secret_for(system)
    if not secret and settings.app_env == "production":
        # Fail closed: an unsigned webhook endpoint in production is a
        # consent-forgery endpoint.
        log.error("webhook secret missing for %s in production", system)
        raise HTTPException(503, f"{system} webhook is not configured")

    try:
        result = webhook_ingest.process(db, system, payload, raw, dict(request.headers), secret)
    except WebhookError as e:
        raise HTTPException(401 if "Signature" in str(e) else 400, str(e))

    return {"status": "processed", "system": system, **result}


@router.post("/salesforce")
async def salesforce(request: Request, db: Session = Depends(get_db)):
    return await _handle("salesforce", request, db)


@router.post("/hubspot")
async def hubspot(request: Request, db: Session = Depends(get_db)):
    return await _handle("hubspot", request, db)


@router.post("/outreach")
async def outreach(request: Request, db: Session = Depends(get_db)):
    return await _handle("outreach", request, db)


@router.post("/highspot")
async def highspot(request: Request, db: Session = Depends(get_db)):
    return await _handle("highspot", request, db)
