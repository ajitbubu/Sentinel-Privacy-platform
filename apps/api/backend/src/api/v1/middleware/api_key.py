"""API key auth for external clients with tier-based rate limiting and IP allowlist."""
import ipaddress

import redis
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.services import api_key_service

api_key_header = APIKeyHeader(name="X-API-Key")
_redis = redis.from_url(settings.redis_url, decode_responses=True)


def _check_ip_allowlist(allowed: list | None, client_ip: str | None) -> bool:
    if not allowed:
        return True  # empty allowlist = any IP
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(addr == ipaddress.ip_address(str(a)) for a in allowed)


def validate_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> dict:
    record = api_key_service.lookup_active_key(api_key, db)
    if record is None:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    client_ip = request.client.host if request.client else None
    if not _check_ip_allowlist(record.get("allowed_ips"), client_ip):
        raise HTTPException(status_code=403, detail="Source IP not allowed for this key")

    key_id = str(record["id"])
    limit = api_key_service.TIER_RATE_LIMITS.get(record["tier"], 100)

    rl_key = f"ratelimit:{key_id}:minute"
    current = _redis.incr(rl_key)
    if current == 1:
        _redis.expire(rl_key, 60)
    if current > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit}/min for {record['tier']} tier)",
            headers={"Retry-After": "60"},
        )

    api_key_service.touch_last_used(key_id, db)

    return {
        "key_id": key_id,
        "client_system": record["client_system"],
        "tier": record["tier"],
        "scopes": record["scopes"],
        "rate_limit": limit,
        "rate_remaining": max(0, limit - current),
    }


def require_scope(scope: str):
    def checker(client: dict = Depends(validate_api_key)) -> dict:
        scopes = client.get("scopes") or []
        if scope not in scopes and "*" not in scopes:
            raise HTTPException(status_code=403, detail=f"API key missing scope: {scope}")
        return client
    return checker
