"""
backend/ws_manager.py — Fan-out WebSocket manager.

The backend holds one list of open connections and broadcasts JSON messages to all of them.
POST /events, POST /heartbeat, and (Phase 3) the detection engine all call
manager.broadcast() after writing.

This module exposes a singleton `manager` that all routes import directly.
No dependency injection needed — there is exactly one manager for the process lifetime.
"""

from fastapi import WebSocket


class ConnectionManager:
    """
    Manages all active WebSocket connections and fans out messages to all of them.

    Thread safety note: broadcast() is called from async def routes running in
    the event loop. Active connections are modified only from the same event loop,
    so no lock is needed. Do not call broadcast() from a sync thread.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept the WebSocket handshake and add to the active list."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a connection from the active list.
        Guard against double-removal (e.g., disconnect called after broadcast() already
        cleaned up a dead connection).
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        """
        Send a JSON message to every connected client.

        Dead connection pattern: collect failed sends in a separate list, then remove
        them AFTER the iteration completes. Never mutate active_connections while
        iterating — that causes silent skip bugs where every other connection is missed.

        Errors during send are silently swallowed — a disconnected client should never
        prevent the message from reaching other clients.
        """
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                # Client disconnected between our last check and now.
                # Add to dead list; remove after iteration.
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Module-level singleton — imported directly by router.py.
# "from backend.ws_manager import manager" is the only import needed.
manager = ConnectionManager()
