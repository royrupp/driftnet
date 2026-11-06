"""
backend/router.py — All REST endpoints and WebSocket endpoint.

All routes use async def so await manager.broadcast() is natural.
DuckDB access uses conn.cursor() on every call — never the connection object directly
— to avoid "Resource In Use Error" under concurrent requests (DuckDB 2.0.0).
"""

import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect, HTTPException, Query

from backend.models import EventBatch, HeartbeatIn, AgentStatus
from backend.ws_manager import manager
from backend.db import rows_as_dicts

router = APIRouter()


@router.get("/")
async def health():
    """BACK-01: Health check. Returns 200 {"status": "ok"} to confirm the server is running."""
    return {"status": "ok"}


@router.post("/events")
async def ingest_events(request: Request, body: EventBatch):
    """
    BACK-03: Ingest a batch of events from the agent.

    Inserts each event into DuckDB using nextval('event_seq') for the primary key.
    nextval() is called in the INSERT — not as a column DEFAULT (DuckDB 2.0.0 rejects
    DEFAULT expressions referencing sequences in CREATE TABLE).

    After all events are inserted, broadcasts {"type": "new_events", "count": N, "ids": [...]}
    to all connected WebSocket clients so the dashboard updates in real-time.
    """
    cur = request.app.state.db.cursor()
    inserted_ids = []

    for event in body.events:
        # Strip tzinfo before inserting — TIMESTAMP column does not accept tz-aware datetimes.
        ts = event.ts.replace(tzinfo=None)

        # Serialize raw_json dict to string — DuckDB JSON columns accept strings, not dicts.
        raw_json_str = json.dumps(event.raw_json) if event.raw_json is not None else None

        row = cur.execute(
            """
            INSERT INTO events VALUES (
                nextval('event_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            ) RETURNING id
            """,
            [
                ts,
                event.host,
                event.event_type,
                event.process_name,
                event.pid,
                event.ppid,
                event.username,
                event.cmdline,
                event.local_ip,
                event.local_port,
                event.remote_ip,
                event.remote_port,
                raw_json_str,
            ],
        ).fetchone()
        inserted_ids.append(row[0])

    await manager.broadcast({
        "type": "new_events",
        "count": len(inserted_ids),
        "ids": inserted_ids,
    })
    return {"ingested": len(body.events)}


@router.post("/heartbeat")
async def heartbeat(request: Request, body: HeartbeatIn):
    """
    BACK-04: Upsert agent status.

    Uses INSERT ... ON CONFLICT DO UPDATE (verified working in DuckDB 2.0.0).
    The second heartbeat from the same agent_id updates rather than duplicating.

    last_seen is set to now() with tzinfo stripped — TIMESTAMP column rejects
    tz-aware datetimes (pytz not installed, so TIMESTAMPTZ is also off the table).

    is_connected is computed at query time: True if last_seen < 15 seconds ago.
    It is NOT stored in the agents table.
    """
    cur = request.app.state.db.cursor()

    # Strip tzinfo — TIMESTAMP column rejects tz-aware datetimes.
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    cur.execute(
        """
        INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (agent_id) DO UPDATE SET
            hostname      = EXCLUDED.hostname,
            os_version    = EXCLUDED.os_version,
            agent_version = EXCLUDED.agent_version,
            last_seen     = EXCLUDED.last_seen,
            cpu_percent   = EXCLUDED.cpu_percent,
            memory_mb     = EXCLUDED.memory_mb
        """,
        [
            body.agent_id,
            body.hostname,
            body.os_version,
            body.agent_version,
            now,
            body.cpu_percent,
            body.memory_mb,
        ],
    )

    # Query back to build AgentStatus response and broadcast.
    cur.execute("SELECT * FROM agents WHERE agent_id = ?", [body.agent_id])
    rows = rows_as_dicts(cur)
    if rows:
        row = rows[0]
        last_seen = row["last_seen"]
        is_connected = (datetime.now() - last_seen) < timedelta(seconds=15)
        status = AgentStatus(
            agent_id=row["agent_id"],
            hostname=row["hostname"],
            os_version=row["os_version"],
            agent_version=row["agent_version"],
            last_seen=last_seen,
            is_connected=is_connected,
            cpu_percent=row["cpu_percent"],
            memory_mb=row["memory_mb"],
        )
        await manager.broadcast({
            "type": "agent_status",
            "data": status.model_dump(mode="json"),
        })

    return {"status": "ok"}


@router.get("/events")
async def get_events(
    request: Request,
    host: str | None = None,
    event_type: str | None = None,
    limit: int = Query(default=100, le=10000),
):
    """
    BACK-05: List recent events, optionally filtered by host and/or event_type.

    Dynamic WHERE clause: starts with an empty list of conditions, adds each
    filter if provided, then joins with AND. This is the standard parameterized
    query builder pattern — no string interpolation, so SQL injection is prevented.
    """
    cur = request.app.state.db.cursor()

    conditions = []
    params: list = []

    if host is not None:
        conditions.append("host = ?")
        params.append(host)
    if event_type is not None:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    cur.execute(f"SELECT * FROM events {where} ORDER BY ts DESC LIMIT ?", params)
    rows = rows_as_dicts(cur)
    return {"events": rows}


@router.get("/alerts")
async def get_alerts(
    request: Request,
    limit: int = Query(default=50, le=1000),
):
    """
    BACK-06: List recent alerts ordered by timestamp descending.

    related_event_ids and llm_report are stored as JSON strings in DuckDB;
    parse them so the response contains native Python types.
    """
    cur = request.app.state.db.cursor()
    cur.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", [limit])
    rows = rows_as_dicts(cur)

    for row in rows:
        row["related_event_ids"] = json.loads(row["related_event_ids"]) if row["related_event_ids"] is not None else []
        row["llm_report"] = json.loads(row["llm_report"]) if row["llm_report"] is not None else None

    return {"alerts": rows}


@router.delete("/alerts")
async def clear_alerts(request: Request):
    """Delete all alerts from the database."""
    cur = request.app.state.db.cursor()
    cur.execute("DELETE FROM alerts")
    await manager.broadcast({"type": "alerts_cleared"})
    return {"cleared": True}


@router.get("/alerts/{alert_id}")
async def get_alert(request: Request, alert_id: int):
    """
    BACK-07: Return a single alert by ID.

    Returns 404 if the alert does not exist.
    JSON fields (related_event_ids, llm_report) are parsed from string to native types.
    """
    cur = request.app.state.db.cursor()
    cur.execute("SELECT * FROM alerts WHERE id = ? LIMIT 1", [alert_id])
    rows = rows_as_dicts(cur)

    if not rows:
        raise HTTPException(status_code=404, detail="Alert not found")

    row = rows[0]
    row["related_event_ids"] = json.loads(row["related_event_ids"]) if row["related_event_ids"] is not None else []
    row["llm_report"] = json.loads(row["llm_report"]) if row["llm_report"] is not None else None
    return row


@router.get("/echo.sh")
async def echo_sh():
    """
    DEMO-02: Serve a harmless shell script for the curl|bash download-exec demo.

    Returns plain text so `curl http://localhost:8000/echo.sh | bash` works.
    The script only prints a message — it does nothing harmful.
    The download_exec detection rule fires on the curl|bash cmdline pattern, not
    on the script contents.
    """
    script = "#!/usr/bin/env bash\necho 'driftnet demo: download_exec pattern detected by Driftnet'\n"
    return Response(content=script, media_type="text/plain")


@router.get("/metrics")
async def get_metrics(request: Request):
    """
    DEMO-05: Resume metrics — event throughput and agent resource usage.

    Returns:
      events_per_minute  — events ingested in the last 60 seconds
      avg_alert_latency_ms — average ms between an event and the alert it triggered
      agent_cpu_percent  — most recently reported agent CPU usage
      agent_memory_mb    — most recently reported agent memory usage (RSS)
    """
    conn = request.app.state.db

    # Events per minute: count events in last 60 seconds
    cutoff_60s = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=60)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM events WHERE ts > ?", [cutoff_60s])
    events_per_minute = cur.fetchone()[0]

    # Average alert latency: for each of the last 20 alerts, find the most recent
    # event on the same host that preceded the alert, then average the deltas (ms).
    cur2 = conn.cursor()
    cur2.execute("""
        WITH recent_alerts AS (
            SELECT ts, host FROM alerts ORDER BY ts DESC LIMIT 20
        ),
        nearest_event AS (
            SELECT a.ts AS alert_ts, MAX(e.ts) AS event_ts
            FROM recent_alerts a
            JOIN events e ON e.host = a.host AND e.ts <= a.ts
            GROUP BY a.ts
        )
        SELECT AVG(epoch_ms(alert_ts) - epoch_ms(event_ts))
        FROM nearest_event
    """)
    row2 = cur2.fetchone()
    avg_latency = round(row2[0], 1) if row2[0] is not None else None

    # Agent resource usage: most recently seen agent
    cur3 = conn.cursor()
    cur3.execute("SELECT cpu_percent, memory_mb FROM agents ORDER BY last_seen DESC LIMIT 1")
    row3 = cur3.fetchone()

    return {
        "events_per_minute": events_per_minute,
        "avg_alert_latency_ms": avg_latency,
        "agent_cpu_percent": row3[0] if row3 else None,
        "agent_memory_mb": round(row3[1], 1) if row3 and row3[1] else None,
    }


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """
    BACK-08: WebSocket endpoint for real-time push.

    receive_text() blocks until the client sends a message or disconnects.
    We do not process client messages in Phase 1 — the connection is receive-only
    from the server's perspective (server pushes, client only pings to keep alive).

    WebSocketDisconnect is raised on clean close (browser tab closed).
    Generic Exception catches network drops.
    """
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keeps connection alive; client sends pings
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
