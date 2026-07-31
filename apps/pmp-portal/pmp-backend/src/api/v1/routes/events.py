"""WebSocket endpoint for live consent updates."""
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from src.config.settings import settings
from src.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws/v1")
async def events(websocket: WebSocket, token: str = Query(...)):
    """Token arrives as a query param — browsers can't set headers on WebSocket."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        await websocket.close(code=4401, reason="Invalid token")
        return

    subject_id = payload.get("sub")
    if not subject_id or payload.get("type") != "pmp_user":
        await websocket.close(code=4403, reason="Not authorised")
        return

    await manager.connect(websocket, subject_id)
    try:
        await websocket.send_json({"type": "connected", "subject_id": subject_id})
        while True:
            await websocket.receive_text()  # keepalive / client pings
    except WebSocketDisconnect:
        manager.disconnect(websocket, subject_id)
