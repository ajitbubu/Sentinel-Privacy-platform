"""WebSocket manager - pushes Redis Pub/Sub events to connected clients."""
import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.config.settings import settings

ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, subject_id: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(subject_id, []).append(ws)

    def disconnect(self, subject_id: str, ws: WebSocket):
        if subject_id in self.connections:
            self.connections[subject_id] = [c for c in self.connections[subject_id] if c != ws]

    async def send_to_subject(self, subject_id: str, message: dict):
        for ws in self.connections.get(subject_id, []):
            await ws.send_json(message)


manager = ConnectionManager()


@ws_router.websocket("/ws/v1")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    # TODO: validate JWT from token query param, extract subject_id
    subject_id = "anonymous"
    await manager.connect(subject_id, ws)
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("channel:consent:updated", "channel:banner:published")

    async def relay():
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws.send_json({"channel": msg["channel"], "data": json.loads(msg["data"])})

    relay_task = asyncio.create_task(relay())
    try:
        while True:
            await ws.receive_text()  # keepalive / subscribe commands
    except WebSocketDisconnect:
        manager.disconnect(subject_id, ws)
        relay_task.cancel()
        await pubsub.close()
