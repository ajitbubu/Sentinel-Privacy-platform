"""Publish domain events to Redis pub/sub (live UI) and the webhook queue.

Two channels deliberately:
  - Pub/sub  -> connected WebSocket clients, sub-10ms, fire-and-forget
  - List     -> durable queue the webhook worker drains, survives restarts

Publishing must never break the request that triggered it: a Redis outage
degrades real-time updates but must not fail a consent write, because the
write is the legally significant act.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import redis

from src.config.settings import settings

log = logging.getLogger(__name__)
_redis = redis.from_url(settings.redis_url, decode_responses=True)

WEBHOOK_QUEUE = "queue:webhook_delivery"


def publish(event_type: str, data: dict) -> str | None:
    event_id = str(uuid.uuid4())
    envelope = {
        "id": event_id, "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    payload = json.dumps(envelope, default=str)
    try:
        _redis.publish(f"channel:{event_type}", payload)
        _redis.publish("channel:all", payload)
        _redis.lpush(WEBHOOK_QUEUE, payload)
        return event_id
    except redis.RedisError as e:
        log.error("event publish failed (%s): %s", event_type, e)
        return None
