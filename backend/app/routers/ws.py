"""WS /ws/vehicles -- live simulated GPS stream."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.simulation import simulator

log = logging.getLogger("ner.ws")
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/vehicles")
async def vehicles_stream(websocket: WebSocket) -> None:
    """Streams fleet positions as they move along their routes.

    On connect you get one `{"type": "snapshot", ...}` frame with every vehicle,
    then a `{"type": "vehicle_positions", ...}` frame every WS_BROADCAST_SECONDS.
    Send `"ping"` to get `{"type": "pong"}` back; anything else is ignored.
    """
    await websocket.accept()
    await simulator.connect(websocket)
    log.info("ws client connected (%d total)", simulator.client_count)
    try:
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "pong", "tick": simulator.tick})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws client error")
    finally:
        await simulator.disconnect(websocket)
        log.info("ws client disconnected (%d left)", simulator.client_count)
