"""Preference center - purposes x channels grid."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.services.consent_service import ConsentService

router = APIRouter()


class PreferenceUpdate(BaseModel):
    purpose_id: str
    channel_id: str
    consent: bool


class PreferencesBody(BaseModel):
    preferences: list[PreferenceUpdate]


@router.get("")
def get_preference_center(
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    return ConsentService(db).preference_center(subject["sub"])


@router.put("")
def update_preferences(
    body: PreferencesBody,
    subject=Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    updated = ConsentService(db).bulk_update(
        subject_id=subject["sub"],
        preferences=[p.model_dump() for p in body.preferences],
    )
    return {"updated": updated, "message": "Preferences updated; syncing to external systems"}
