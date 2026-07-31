"""WebSocket fan-out backed by Redis pub/sub.

One Redis subscription per process (not per client) relays to every connected
socket, so N clients cost one subscription rather than N.
"""
import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from src.config.settings import settings

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket, subject_id: str) -> None:
        await ws.accept()
        self._connections.setdefault(subject_id, set()).add(ws)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._relay())

    def disconnect(self, ws: WebSocket, subject_id: str) -> None:
        conns = self._connections.get(subject_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self._connections.pop(subject_id, None)

    async def send_to(self, subject_id: str, message: dict) -> None:
        dead = []
        for ws in self._connections.get(subject_id, set()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, subject_id)

    async def _relay(self) -> None:
        """Single Redis subscription relaying events to the owning subject."""
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe("channel:all")
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg["data"])
                except (ValueError, KeyError):
                    continue
                subject_id = (event.get("data") or {}).get("subject_id")
                if subject_id:
                    await self.send_to(subject_id, event)
        except Exception as e:
            log.error("websocket relay stopped: %s", e)


manager = ConnectionManager()
