"""BACK-08: WebSocket /ws broadcasts new_events messages when POST /events is called."""


def test_ws_broadcast(client, sample_event):
    """
    BACK-08: A connected WebSocket client receives a {"type": "new_events"} message
    immediately after POST /events completes.

    TestClient.websocket_connect() runs the WebSocket handler in a thread;
    the HTTP POST triggers broadcast() which sends to the WebSocket thread.
    This is the standard FastAPI testing pattern for WebSocket broadcast.

    Verifies:
    - type == "new_events" (not new_alert or agent_status)
    - count == 1 (one event in the batch)
    - len(ids) == 1 (one event ID returned from the INSERT ... RETURNING id)
    """
    # TestClient supports both HTTP and WebSocket in a single with block.
    with client.websocket_connect("/ws") as ws:
        response = client.post("/events", json=sample_event)
        assert response.status_code == 200

        data = ws.receive_json()
        assert data["type"] == "new_events"
        assert data["count"] == 1
        assert len(data["ids"]) == 1
