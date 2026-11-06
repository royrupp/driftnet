"""
backend/db.py — DuckDB schema owner and query helpers.

This file has two responsibilities:
1. init_schema(): runs all DDL at startup to create tables, sequences, and indexes.
2. rows_as_dicts(): converts DuckDB cursor results to list of dicts for JSON responses.

The DB_PATH constant names the persistent file. main.py passes its own db_path to
override this in tests (":memory:" gives each test a fresh isolated database).
"""

import duckdb

# Production database file path. main.py's create_app(db_path=...) overrides this for tests.
DB_PATH = "driftnet.duckdb"


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Create all tables, sequences, and indexes if they don't already exist.

    Uses conn.cursor() — not conn directly — because routes also call cursor() and
    DuckDB 2.0.0 raises "Resource In Use Error" when conn.execute() is called
    simultaneously from multiple threads. cursor() creates an independent cursor
    object that serializes access correctly.

    CRITICAL — do NOT put DEFAULT nextval('event_seq') in CREATE TABLE.
    DuckDB 2.0.0 rejects DEFAULT expressions that reference sequences in table DDL.
    nextval() is called in INSERT statements only (see router.py).

    CRITICAL — do NOT use TIMESTAMPTZ. It requires pytz which is not installed.
    All timestamps use TIMESTAMP and are treated as UTC by convention.
    """
    cur = conn.cursor()

    # Sequences for auto-incrementing primary keys.
    # nextval('event_seq') is called in INSERT — NOT as a column DEFAULT.
    cur.execute("CREATE SEQUENCE IF NOT EXISTS event_seq START 1")
    cur.execute("CREATE SEQUENCE IF NOT EXISTS alert_seq START 1")

    # Events table (BACK-02): one row per security event from the agent.
    # event_type is VARCHAR (not ENUM) so we can add types without schema migration.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id           BIGINT PRIMARY KEY,
            ts           TIMESTAMP NOT NULL,
            host         VARCHAR NOT NULL,
            event_type   VARCHAR NOT NULL,
            process_name VARCHAR,
            pid          INTEGER,
            ppid         INTEGER,
            username     VARCHAR,
            cmdline      VARCHAR,
            local_ip     VARCHAR,
            local_port   INTEGER,
            remote_ip    VARCHAR,
            remote_port  INTEGER,
            raw_json     JSON
        )
    """)

    # Alerts table: one row per detection rule firing.
    # related_event_ids is a JSON array of event IDs: [1, 2, 3].
    # llm_report is null until Phase 5 (Ollama investigation) populates it.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id                BIGINT PRIMARY KEY,
            ts                TIMESTAMP NOT NULL,
            host              VARCHAR NOT NULL,
            rule_id           VARCHAR NOT NULL,
            severity          VARCHAR NOT NULL,
            description       VARCHAR,
            mitre_id          VARCHAR,
            related_event_ids JSON,
            llm_report        JSON
        )
    """)

    # Agents table: one row per agent_id, upserted on each heartbeat.
    # last_seen and cpu/memory are updated on every heartbeat.
    # is_connected is NOT stored here — it's computed at query time.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id      VARCHAR PRIMARY KEY,
            hostname      VARCHAR NOT NULL,
            os_version    VARCHAR,
            agent_version VARCHAR,
            last_seen     TIMESTAMP,
            cpu_percent   DOUBLE,
            memory_mb     DOUBLE
        )
    """)

    # Indexes for common query patterns.
    # GET /events typically filters by host or orders by ts.
    # GET /alerts orders by ts.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts   ON events(ts)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_host ON events(host)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts_ts   ON alerts(ts)")


def rows_as_dicts(cursor) -> list[dict]:
    """
    Convert DuckDB cursor results to a list of dicts.

    DuckDB fetchall() returns tuples — column names come from cursor.description.
    cursor.description is a list of (name, type_code, ...) tuples, so d[0] is the
    column name. This is the standard Python DB-API 2.0 pattern.

    Example:
        cur.execute("SELECT id, host FROM events")
        rows = rows_as_dicts(cur)
        # [{"id": 1, "host": "macbook"}, ...]
    """
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
