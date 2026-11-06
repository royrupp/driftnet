"""
Unit tests for agent/collector.py

Tests run without real psutil calls — all psutil functions are mocked.
"""

from unittest.mock import patch, MagicMock
import psutil
import pytest

from agent.collector import (
    snapshot_processes,
    diff_processes,
    snapshot_connections,
    diff_connections,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc_mock(pid, ppid, name, cmdline, username, create_time):
    """Return a mock object whose .info dict matches the six ATTRS."""
    m = MagicMock()
    m.info = {
        "pid": pid,
        "ppid": ppid,
        "name": name,
        "cmdline": cmdline,
        "username": username,
        "create_time": create_time,
    }
    return m


def _make_conn_mock(laddr_ip, laddr_port, raddr_ip, raddr_port, status, pid=100, fd=5):
    """Return a mock namedtuple-like connection object."""
    conn = MagicMock()
    if laddr_ip is not None:
        conn.laddr = MagicMock(ip=laddr_ip, port=laddr_port)
    else:
        conn.laddr = None
    if raddr_ip is not None:
        conn.raddr = MagicMock(ip=raddr_ip, port=raddr_port)
    else:
        conn.raddr = None
    conn.status = status
    conn.pid = pid
    conn.fd = fd
    return conn


# ---------------------------------------------------------------------------
# snapshot_processes tests
# ---------------------------------------------------------------------------

def test_snapshot_processes_returns_dict_keyed_by_pid_create_time():
    """snapshot_processes() should return a dict with (pid, create_time) tuple keys."""
    mock_procs = [
        _make_proc_mock(100, 1, "bash", ["/bin/bash"], "alice", 1700000000.0),
        _make_proc_mock(200, 1, "python3", ["python3", "script.py"], "bob", 1700000001.0),
    ]
    with patch("psutil.process_iter", return_value=mock_procs):
        result = snapshot_processes()

    assert isinstance(result, dict)
    assert (100, 1700000000.0) in result
    assert (200, 1700000001.0) in result


def test_snapshot_processes_values_contain_expected_keys():
    """Each value in the dict should have all six ATTRS keys."""
    mock_procs = [
        _make_proc_mock(42, 1, "ls", ["ls", "-la"], "root", 1700000005.0),
    ]
    with patch("psutil.process_iter", return_value=mock_procs):
        result = snapshot_processes()

    info = result[(42, 1700000005.0)]
    for key in ("pid", "ppid", "name", "cmdline", "username", "create_time"):
        assert key in info, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# diff_processes tests
# ---------------------------------------------------------------------------

def test_diff_processes_empty_prev_returns_all_as_new():
    """diff_processes({}, curr) returns a list with one entry per key in curr."""
    curr = {
        (100, 1.0): {"pid": 100, "ppid": 1, "name": "bash", "cmdline": ["/bin/bash"], "username": "alice", "create_time": 1.0},
        (200, 2.0): {"pid": 200, "ppid": 1, "name": "python3", "cmdline": ["python3"], "username": "bob", "create_time": 2.0},
    }
    events = diff_processes({}, curr)
    assert len(events) == 2
    for ev in events:
        assert ev["event_type"] == "process_start"


def test_diff_processes_no_new_keys_returns_empty():
    """diff_processes(prev, curr) where curr == prev should return []."""
    prev = {
        (100, 1.0): {"pid": 100, "ppid": 1, "name": "bash", "cmdline": [], "username": "alice", "create_time": 1.0},
    }
    curr = dict(prev)
    assert diff_processes(prev, curr) == []


def test_diff_processes_one_new_key_returns_one_event():
    """diff_processes returns exactly one event when curr has one new key."""
    prev = {
        (100, 1.0): {"pid": 100, "ppid": 1, "name": "bash", "cmdline": [], "username": "alice", "create_time": 1.0},
    }
    curr = {
        (100, 1.0): prev[(100, 1.0)],
        (200, 2.0): {"pid": 200, "ppid": 1, "name": "python3", "cmdline": ["python3", "-c", "x=1"], "username": "bob", "create_time": 2.0},
    }
    events = diff_processes(prev, curr)
    assert len(events) == 1
    assert events[0]["event_type"] == "process_start"


def test_diff_processes_event_contains_required_fields():
    """Events from diff_processes must have all required fields."""
    curr = {
        (99, 9.0): {"pid": 99, "ppid": 2, "name": "curl", "cmdline": ["curl", "http://x.com"], "username": "user1", "create_time": 9.0},
    }
    events = diff_processes({}, curr)
    assert len(events) == 1
    ev = events[0]
    for field in ("event_type", "pid", "ppid", "process_name", "username", "cmdline", "raw_json"):
        assert field in ev, f"Missing field: {field}"


def test_diff_processes_cmdline_joined_when_nonempty():
    """cmdline should be a space-joined string when psutil cmdline list is non-empty."""
    curr = {
        (10, 1.0): {"pid": 10, "ppid": 1, "name": "ls", "cmdline": ["ls", "-la", "/tmp"], "username": "root", "create_time": 1.0},
    }
    events = diff_processes({}, curr)
    assert events[0]["cmdline"] == "ls -la /tmp"


def test_diff_processes_cmdline_none_when_empty():
    """cmdline should be None when psutil returns an empty list."""
    curr = {
        (11, 1.0): {"pid": 11, "ppid": 1, "name": "kernel_task", "cmdline": [], "username": "root", "create_time": 1.0},
    }
    events = diff_processes({}, curr)
    assert events[0]["cmdline"] is None


def test_diff_processes_cmdline_none_when_none():
    """cmdline should be None when psutil returns None (AccessDenied scenario)."""
    curr = {
        (12, 1.0): {"pid": 12, "ppid": 1, "name": "securityd", "cmdline": None, "username": "root", "create_time": 1.0},
    }
    events = diff_processes({}, curr)
    assert events[0]["cmdline"] is None


# ---------------------------------------------------------------------------
# snapshot_connections tests
# ---------------------------------------------------------------------------

def test_snapshot_connections_returns_empty_on_access_denied():
    """snapshot_connections() must return {} (no exception) when AccessDenied."""
    with patch("psutil.net_connections", side_effect=psutil.AccessDenied(pid=0)):
        result = snapshot_connections()
    assert result == {}


def test_snapshot_connections_returns_dict_keyed_by_tuple():
    """snapshot_connections() returns a dict keyed by 5-tuple."""
    mock_conn = _make_conn_mock("127.0.0.1", 8080, "93.184.216.34", 443, "ESTABLISHED")
    with patch("psutil.net_connections", return_value=[mock_conn]):
        result = snapshot_connections()

    expected_key = ("127.0.0.1", 8080, "93.184.216.34", 443, "ESTABLISHED")
    assert expected_key in result


# ---------------------------------------------------------------------------
# diff_connections tests
# ---------------------------------------------------------------------------

def test_diff_connections_empty_prev_returns_all_as_new():
    """diff_connections({}, curr) returns a list with event_type='network_conn' for every key."""
    conn1 = _make_conn_mock("127.0.0.1", 8080, "10.0.0.1", 80, "ESTABLISHED")
    conn2 = _make_conn_mock("0.0.0.0", 22, None, None, "LISTEN")

    curr = {
        ("127.0.0.1", 8080, "10.0.0.1", 80, "ESTABLISHED"): conn1,
        ("0.0.0.0", 22, None, None, "LISTEN"): conn2,
    }
    events = diff_connections({}, curr)
    assert len(events) == 2
    for ev in events:
        assert ev["event_type"] == "network_conn"


def test_diff_connections_event_contains_required_fields():
    """Events from diff_connections must have all required fields."""
    conn = _make_conn_mock("192.168.1.1", 443, "1.2.3.4", 9000, "TIME_WAIT")
    curr = {("192.168.1.1", 443, "1.2.3.4", 9000, "TIME_WAIT"): conn}
    events = diff_connections({}, curr)
    assert len(events) == 1
    ev = events[0]
    for field in ("event_type", "local_ip", "local_port", "remote_ip", "remote_port", "raw_json"):
        assert field in ev, f"Missing field: {field}"


def test_diff_connections_raw_json_has_status_pid_fd():
    """raw_json in network event must contain status, pid, fd keys."""
    conn = _make_conn_mock("10.0.0.1", 1234, "8.8.8.8", 53, "SYN_SENT", pid=777, fd=12)
    curr = {("10.0.0.1", 1234, "8.8.8.8", 53, "SYN_SENT"): conn}
    events = diff_connections({}, curr)
    rj = events[0]["raw_json"]
    assert "status" in rj
    assert "pid" in rj
    assert "fd" in rj
    assert rj["pid"] == 777
    assert rj["fd"] == 12
