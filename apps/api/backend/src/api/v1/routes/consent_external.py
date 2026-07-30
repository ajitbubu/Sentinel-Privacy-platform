"""Third-party consent submission (Salesforce, HubSpot, Outreach, Highspot, custom)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.api.v1.middleware.api_key import validate_api_key
from src.config.database import get_db
from src.services.consent_ingest import ConsentIngestService

router = APIRouter()


class ExternalConsent(BaseModel):
    email: EmailStr
    purposes: list[str]
    channels: list[str] = ["email"]
    consent: bool
    source: str  # salesforce | hubspot | outreach | highspot | custom_app
    source_system_id: str | None = None
    legal_basis: str = "consent"
    timestamp: str | None = None
    metadata: dict = {}


class BulkConsent(BaseModel):
    consents: list[ExternalConsent]


@router.post("", status_code=201)
def submit_consent(
    body: ExternalConsent,
    client=Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    return ConsentIngestService(db).ingest(body.model_dump(), client_id=client["client_id"])


@router.post("/bulk", status_code=202)
def submit_bulk(
    body: BulkConsent,
    client=Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    return ConsentIngestService(db).ingest_bulk(
        [c.model_dump() for c in body.consents], client_id=client["client_id"]
    )
