"""API key administration (DPO/admin only). Keys are shown in plaintext exactly once."""
import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.v1.middleware.auth import require_permission
from src.config.database import get_db
from src.services.audit_service import log_audit

router = APIRouter()

KEY_PREFIX = "sk_live_"
VALID_SYSTEMS = {"salesforce", "hubspot", "outreach", "highspot", "custom"}


class CreateKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    client_system: str
    tier: str = "standard"
    scopes: list[str] = ["consent:write"]
    allowed_ips: list[str] = []
    expires_at: datetime | None = None


class CreateKeyResponse(BaseModel):
    id: str
    api_key: str  # shown once, never retrievable again
    key_prefix: str
    name: str
    client_system: str
    tier: str
    warning: str = "Store this key now — it cannot be retrieved again."


@router.post("", response_model=CreateKeyResponse, status_code=201)
def create_api_key(
    body: CreateKeyRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("write:webhook")),
):
    if body.client_system not in VALID_SYSTEMS:
        raise HTTPException(400, f"client_system must be one of {sorted(VALID_SYSTEMS)}")
    if body.tier not in {"standard", "premium", "enterprise"}:
        raise HTTPException(400, "tier must be standard, premium, or enterprise")

    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()

    key_id = db.execute(
        text("""
            INSERT INTO api_keys (name, client_system, key_hash, key_prefix, tier,
                                  scopes, allowed_ips, expires_at, created_by_user_id)
            VALUES (:name, :sys, :kh, :prefix, :tier,
                    :scopes, CAST(:ips AS INET[]), :exp, :uid)
            RETURNING id
        """),
        {
            "name": body.name, "sys": body.client_system, "kh": key_hash,
            "prefix": raw[:12], "tier": body.tier, "scopes": body.scopes,
            "ips": body.allowed_ips or [], "exp": body.expires_at, "uid": user["sub"],
        },
    ).scalar()
    db.commit()

    log_audit(db, entity_type="api_key", entity_id=str(key_id), action="create",
              actor_id=user["sub"], new_values={"name": body.name, "tier": body.tier,
                                                "client_system": body.client_system})

    return CreateKeyResponse(
        id=str(key_id), api_key=raw, key_prefix=raw[:12],
        name=body.name, client_system=body.client_system, tier=body.tier,
    )


@router.get("")
def list_api_keys(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("read:webhook")),
):
    """List keys. Never returns the key itself — only the prefix for identification."""
    rows = db.execute(text("""
        SELECT id, name, client_system, key_prefix, tier, scopes, is_active,
               expires_at, last_used_at, revoked_at, created_at
        FROM api_keys
        ORDER BY created_at DESC
    """)).mappings().all()
    return {"keys": [dict(r) for r in rows], "total": len(rows)}


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/{key_id}/revoke", status_code=200)
def revoke_api_key(
    key_id: str,
    body: RevokeRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("write:webhook")),
):
    result = db.execute(
        text("""
            UPDATE api_keys
            SET is_active = FALSE, revoked_at = NOW(), revoked_reason = :reason,
                updated_at = NOW()
            WHERE id = CAST(:kid AS UUID) AND revoked_at IS NULL
            RETURNING id
        """),
        {"kid": key_id, "reason": body.reason},
    ).scalar()
    if not result:
        raise HTTPException(404, "Key not found or already revoked")
    db.commit()

    log_audit(db, entity_type="api_key", entity_id=key_id, action="revoke",
              actor_id=user["sub"], new_values={"reason": body.reason})
    return {"id": key_id, "status": "revoked", "reason": body.reason}
