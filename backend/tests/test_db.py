"""BACK-02: DuckDB schema has all required normalized columns."""

import duckdb

from backend.db import init_schema


def test_schema_tables():
    """
    BACK-02: After init_schema(), the three required tables exist in DuckDB.

    Uses an isolated in-memory connection — no dependency on the running app.
    Tests the schema DDL directly so failures are localized to db.py.
    """
    conn = duckdb.connect(":memory:")
    init_schema(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    )
    tables = {row[0] for row in cur.fetchall()}

    assert "events" in tables, f"events table missing; found: {tables}"
    assert "alerts" in tables, f"alerts table missing; found: {tables}"
    assert "agents" in tables, f"agents table missing; found: {tables}"


def test_schema_events_columns():
    """
    BACK-02: events table has all 14 required columns.

    All columns must be present for the full INSERT in POST /events to work.
    If any column is missing, the INSERT will fail with an error that is hard to debug
    (DuckDB raises a column count mismatch, not a "column not found" error on positional inserts).
    """
    conn = duckdb.connect(":memory:")
    init_schema(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='events' AND table_schema='main'"
    )
    cols = {row[0] for row in cur.fetchall()}

    required = {
        "id", "ts", "host", "event_type",
        "process_name", "pid", "ppid", "username", "cmdline",
        "local_ip", "local_port", "remote_ip", "remote_port",
        "raw_json",
    }
    assert required.issubset(cols), f"Missing columns in events: {required - cols}"


def test_schema_agents_columns():
    """
    BACK-02: agents table has all 7 columns required for heartbeat upsert.

    The upsert in POST /heartbeat inserts all 7 columns by position.
    If the schema drifts, the upsert fails at runtime.
    """
    conn = duckdb.connect(":memory:")
    init_schema(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='agents' AND table_schema='main'"
    )
    cols = {row[0] for row in cur.fetchall()}

    required = {
        "agent_id", "hostname", "os_version", "agent_version",
        "last_seen", "cpu_percent", "memory_mb",
    }
    assert required.issubset(cols), f"Missing columns in agents: {required - cols}"
