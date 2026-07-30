"""Inbound webhook receivers with HMAC signature verification."""
import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.services.consent_ingest import ConsentIngestService

router = APIRouter()


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/salesforce")
async def salesforce_webhook(
    request: Request,
    x_salesforce_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if settings.salesforce_webhook_secret and not verify_signature(
        body, x_salesforce_signature, settings.salesforce_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = await request.json()
    ConsentIngestService(db).ingest_from_salesforce(payload)
    return {"status": "success", "message": "Webhook received and queued"}


@router.post("/hubspot")
async def hubspot_webhook(
    request: Request,
    x_hubspot_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if settings.hubspot_webhook_secret and not verify_signature(
        body, x_hubspot_signature, settings.hubspot_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = await request.json()
    ConsentIngestService(db).ingest_from_hubspot(payload)
    return {"status": "success", "message": "Webhook processed"}


@router.post("/outreach")
async def outreach_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    ConsentIngestService(db).ingest_from_outreach(payload)
    return {"status": "success"}


@router.post("/highspot")
async def highspot_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    ConsentIngestService(db).ingest_from_highspot(payload)
    return {"status": "success"}
