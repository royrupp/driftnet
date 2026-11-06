"""
backend/detection/engine.py — Detection engine: runs all rules against active hosts.

Exports:
  write_alert(conn, alert_dict) -> int   — writes one alert row, returns new ID
  run_detection_cycle(conn) -> None      — async; called from main.py every 5 seconds
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

import duckdb

from backend.detection.rules import (
    unusual_listener,
    reverse_shell,
    download_exec,
    sudo_bruteforce,
    shell_unusual_parent,
)
from backend.investigator import investigate
from backend.ws_manager import manager

RULES = [unusual_listener, reverse_shell, download_exec, sudo_bruteforce, shell_unusual_parent]
log = logging.getLogger("driftnet.detection")


def write_alert(conn: duckdb.DuckDBPyConnection, alert_dict: dict) -> int:
    """Write alert dict to DuckDB alerts table. Returns the new alert ID."""
    cur = conn.cursor()
    row = cur.execute(
        """
        INSERT INTO alerts VALUES (
            nextval('alert_seq'), ?, ?, ?, ?, ?, ?, ?, ?
        ) RETURNING id
        """,
        [
            alert_dict["ts"],
            alert_dict["host"],
            alert_dict["rule_id"],
            alert_dict["severity"],
            alert_dict["description"],
            alert_dict["mitre_id"],
            json.dumps(alert_dict.get("related_event_ids", [])),
            None,  # llm_report — Phase 5
        ],
    ).fetchone()
    return row[0]


async def run_detection_cycle(conn: duckdb.DuckDBPyConnection) -> None:
    """Run all rules against all active hosts. Called from detection_loop in main.py."""
    AGENT_LOOKBACK_SECONDS = 30
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=AGENT_LOOKBACK_SECONDS)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT agent_id FROM agents WHERE last_seen > ?", [cutoff])
    hosts = [r[0] for r in cur.fetchall()]

    for host in hosts:
        for rule_module in RULES:
            try:
                result = rule_module.run(conn, host)
                if result is not None:
                    alert_id = write_alert(conn, result)
                    asyncio.create_task(investigate(conn, alert_id, host, result))
                    await manager.broadcast({
                        "type": "new_alert",
                        "alert_id": alert_id,
                        "rule_id": result["rule_id"],
                        "severity": result["severity"],
                        "host": host,
                    })
                    log.info(
                        "Alert %d fired: rule=%s host=%s severity=%s",
                        alert_id, result["rule_id"], host, result["severity"],
                    )
            except Exception as exc:
                log.warning("Rule %s failed for host %s: %s", rule_module.__name__, host, exc)
