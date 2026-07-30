"""Publish real-time events to Redis Pub/Sub (<1s sync backbone)."""
import json

import redis

from src.config.settings import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)


def publish_event(channel: str, payload: dict) -> None:
    """Fire-and-forget publish. Subscribers: WebSocket manager, webhook worker."""
    try:
        _redis.publish(f"channel:{channel}", json.dumps(payload, default=str))
    except redis.RedisError:
        # Never block the request path on event delivery
        pass
