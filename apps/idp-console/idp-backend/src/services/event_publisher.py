"""Publish domain events onto the webhook delivery queue.

Events are consumed by `src.workers.webhook_worker`, which fans each one out to
every active webhook registered for its `type`. The caller's payload is kept
under `data` rather than merged into the top level, since a payload field
(e.g. a banner's own `type`) could otherwise collide with the event's `type`.
"""
import json
import uuid
from datetime import datetime, timezone

import redis

from src.config.settings import settings

QUEUE = "queue:webhook_delivery"

_redis = redis.from_url(settings.redis_url, decode_responses=True)


def publish(event_type: str, data: dict) -> str:
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    _redis.lpush(QUEUE, json.dumps(event, default=str))
    return event_id
