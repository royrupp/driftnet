"""
agent/collector.py — psutil process and network collectors with diff logic.

Provides:
  snapshot_processes()    -> dict[tuple, dict]
  diff_processes()        -> list[dict]
  snapshot_connections()  -> dict[tuple, conn]
  diff_connections()      -> list[dict]
"""

import psutil

ATTRS = ['pid', 'ppid', 'name', 'cmdline', 'username', 'create_time']


def snapshot_processes() -> dict:
    """
    Return a snapshot of all running processes keyed by (pid, create_time).

    Uses psutil.process_iter() with ATTRS for efficient batch access.
    Processes that disappear mid-iteration or are access-denied are skipped.
    """
    result = {}
    for proc in psutil.process_iter(ATTRS, ad_value=None):
        try:
            info = proc.info
            key = (info['pid'], info.get('create_time'))
            result[key] = info
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return result


def diff_processes(prev: dict, curr: dict) -> list:
    """
    Return a list of process_start event dicts for each process in curr not in prev.

    Events contain: event_type, pid, ppid, process_name, username, cmdline, raw_json.
    cmdline is a space-joined string when non-empty, None otherwise.
    """
    new_keys = set(curr) - set(prev)
    events = []
    for key in new_keys:
        info = curr[key]
        cmdline_raw = info.get('cmdline')
        cmdline = ' '.join(cmdline_raw) if cmdline_raw else None
        events.append({
            "event_type": "process_start",
            "pid": info['pid'],
            "ppid": info.get('ppid'),
            "process_name": info.get('name'),
            "username": info.get('username'),
            "cmdline": cmdline,
            "raw_json": info,
        })
    return events


def _connection_key(conn) -> tuple:
    """Build a 5-tuple key from a psutil connection object."""
    laddr = conn.laddr
    raddr = conn.raddr
    return (
        laddr.ip if laddr else None,
        laddr.port if laddr else None,
        raddr.ip if raddr else None,
        raddr.port if raddr else None,
        str(conn.status),
    )


def snapshot_connections() -> dict:
    """
    Return a snapshot of active inet connections keyed by (laddr_ip, laddr_port, raddr_ip, raddr_port, status).

    Returns {} gracefully when psutil.AccessDenied is raised (non-sudo).
    Satisfies AGNT-07: graceful degradation without sudo.
    """
    try:
        conns = psutil.net_connections(kind='inet')
    except psutil.AccessDenied:
        return {}
    return {_connection_key(c): c for c in conns}


def diff_connections(prev: dict, curr: dict) -> list:
    """
    Return a list of network_conn event dicts for each connection in curr not in prev.

    Events contain: event_type, local_ip, local_port, remote_ip, remote_port, raw_json.
    raw_json contains status, pid, fd from the connection object.
    """
    new_keys = set(curr) - set(prev)
    events = []
    for key in new_keys:
        conn = curr[key]
        laddr = conn.laddr
        raddr = conn.raddr
        events.append({
            "event_type": "network_conn",
            "local_ip": laddr.ip if laddr else None,
            "local_port": laddr.port if laddr else None,
            "remote_ip": raddr.ip if raddr else None,
            "remote_port": raddr.port if raddr else None,
            "raw_json": {
                "status": str(conn.status),
                "pid": conn.pid,
                "fd": conn.fd,
            },
        })
    return events
