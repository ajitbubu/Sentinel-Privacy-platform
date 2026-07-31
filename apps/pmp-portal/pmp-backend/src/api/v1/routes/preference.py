"""Preference centre — the purposes x channels grid."""
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import get_current_subject
from src.config.database import get_db
from src.repository import consent_repository as repo
from src.services import consent_service

router = APIRouter()


class Preference(BaseModel):
    purpose: str
    channel: str
    granted: bool


class UpdateRequest(BaseModel):
    preferences: list[Preference] = Field(min_length=1, max_length=100)
    reason: str | None = None


@router.get("")
def get_preference_centre(user: dict = Depends(get_current_subject),
                          db: Session = Depends(get_db)):
    """Grouped by purpose so the UI renders one card per purpose."""
    rows = repo.preference_matrix(db, user["sub"])
    grouped: dict[str, dict] = {}
    for row in rows:
        pid = str(row["purpose_id"])
        if pid not in grouped:
            grouped[pid] = {
                "purpose_id": pid,
                "purpose": row["purpose"],
                "slug": row["purpose_slug"],
                "description": row["description"],
                "is_mandatory": row["is_mandatory"],
                "requires_explicit_consent": row["requires_explicit_consent"],
                "retention_days": row["retention_period_days"],
                "channels": [],
            }
        grouped[pid]["channels"].append({
            "channel_id": str(row["channel_id"]),
            "channel": row["channel"],
            "type": row["channel_type"],
            "consent_id": str(row["consent_id"]) if row["consent_id"] else None,
            "status": row["status"],
            "granted": row["status"] == "granted",
            "granted_at": row["granted_at"],
            "withdrawn_at": row["withdrawn_at"],
            "source": row["source_system"],
        })
    return {"purposes": list(grouped.values())}


@router.put("")
def update_preferences(body: UpdateRequest, request: Request,
                       user: dict = Depends(get_current_subject),
                       db: Session = Depends(get_db)):
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return consent_service.set_many(
        db, subject_id=user["sub"],
        preferences=[p.model_dump() for p in body.preferences],
        source_system="PMP", actor_id=user["sub"], source_ip=ip,
        user_agent=request.headers.get("user-agent"), reason=body.reason,
    )
