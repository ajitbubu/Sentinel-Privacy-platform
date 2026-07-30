"""API key auth for external clients with per-key rate limiting."""
import hashlib

import redis
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key")
_redis = redis.from_url(settings.redis_url, decode_responses=True)

RATE_LIMIT_PER_MINUTE = 100


def validate_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> dict:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    # TODO: look up key_hash in api_keys table; placeholder accepts a dev key
    client = {"client_id": key_hash[:12], "tier": "standard"}

    # Sliding-window rate limit
    rl_key = f"ratelimit:{client['client_id']}:minute"
    current = _redis.incr(rl_key)
    if current == 1:
        _redis.expire(rl_key, 60)
    if current > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return client
