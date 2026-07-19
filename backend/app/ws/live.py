"""WS /ws/session/{session_id}: push live detections + alerts to the dashboard."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..runtime import hub

router = APIRouter()


@router.websocket("/ws/session/{session_id}")
async def live(ws: WebSocket, session_id: str) -> None:
    await hub.connect(session_id, ws)
    try:
        while True:
            # Dashboard is receive-only; keep the socket alive and ignore pings.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(session_id, ws)
    except Exception:
        await hub.disconnect(session_id, ws)
