"""
backend/investigator.py — LLM investigator for security alerts.

Automatically analyzes alerts using a local Ollama instance. When the detection
engine writes an alert, it fires a background asyncio task (investigate) that
gathers context events, calls Ollama, parses the structured JSON response, and
stores the report in alerts.llm_report. Ollama unavailability never blocks detection.

Public API:
    gather_context(conn, alert_id, host) -> dict
    build_prompt(context) -> str
    parse_report(raw_text) -> dict
    write_report(conn, alert_id, report) -> None
    investigate(conn, alert_id, host, alert_dict) -> None   # async coroutine
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta

import duckdb
import ollama

log = logging.getLogger("driftnet.investigator")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
CONTEXT_WINDOW_EVENTS = 20

SYSTEM_PROMPT = (
    "You are a security analyst AI. You will be given details about a security alert "
    "and recent events from the same host. Analyze the alert and return a structured "
    "JSON report with exactly these fields:\n"
    "- summary: a 1-2 sentence plain-English description of what happened and why it is suspicious\n"
    "- timeline: a list of key events in chronological order (strings)\n"
    "- severity: one of \"critical\", \"high\", \"medium\", \"low\"\n"
    "- techniques: list of MITRE ATT&CK technique IDs that apply\n"
    "- next_steps: list of recommended remediation steps (strings)\n\n"
    "Return ONLY valid JSON. Do not include any explanation outside the JSON object."
)


def gather_context(conn: duckdb.DuckDBPyConnection, alert_id: int, host: str) -> dict:
    """
    Gather alert details and related events from DuckDB.

    Returns a dict with keys 'alert' and 'events', or {} if the alert is not found.
    Events are filtered to the same host within ±2 minutes of the alert timestamp.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id, ts, host, rule_id, severity, description, mitre_id FROM alerts WHERE id=?",
        [alert_id],
    )
    row = cur.fetchone()
    if row is None:
        return {}

    alert = {
        "id": row[0],
        "ts": row[1],
        "host": row[2],
        "rule_id": row[3],
        "severity": row[4],
        "description": row[5],
        "mitre_id": row[6],
    }

    # Handle both datetime objects and ISO string timestamps from DuckDB
    alert_ts = alert["ts"]
    if isinstance(alert_ts, str):
        alert_ts = datetime.fromisoformat(alert_ts)
    if hasattr(alert_ts, "tzinfo") and alert_ts.tzinfo is not None:
        alert_ts = alert_ts.replace(tzinfo=None)

    start = alert_ts - timedelta(minutes=2)
    end = alert_ts + timedelta(minutes=2)

    cur2 = conn.cursor()
    cur2.execute(
        """
        SELECT id, ts, event_type, process_name, pid, username, cmdline,
               local_ip, local_port, remote_ip, remote_port
        FROM events
        WHERE host=? AND ts BETWEEN ? AND ?
        ORDER BY ts
        LIMIT ?
        """,
        [host, start, end, CONTEXT_WINDOW_EVENTS],
    )
    events = []
    for r in cur2.fetchall():
        events.append({
            "id": r[0],
            "ts": str(r[1]),
            "event_type": r[2],
            "process_name": r[3],
            "pid": r[4],
            "username": r[5],
            "cmdline": r[6],
            "local_ip": r[7],
            "local_port": r[8],
            "remote_ip": r[9],
            "remote_port": r[10],
        })

    return {"alert": alert, "events": events}


def build_prompt(context: dict) -> str:
    """Build the user message prompt for Ollama from alert context."""
    alert = context["alert"]
    events = context.get("events", [])

    alert_line = (
        f"rule={alert.get('rule_id')} severity={alert.get('severity')} "
        f"mitre={alert.get('mitre_id')} host={alert.get('host')} "
        f"ts={alert.get('ts')} description={alert.get('description')}"
    )

    event_lines = []
    for ev in events:
        cmdline = (ev.get("cmdline") or "")[:120]
        parts = [
            str(ev.get("ts", "")),
            str(ev.get("event_type", "")),
            str(ev.get("process_name", "")),
            cmdline,
        ]
        event_lines.append(" | ".join(p for p in parts if p))

    prompt = f"Alert: {alert_line}\n\nRecent events on this host:\n"
    if event_lines:
        prompt += "\n".join(event_lines)
    else:
        prompt += "(no related events)"
    return prompt


def parse_report(raw_text: str) -> dict:
    """
    Parse structured JSON report from Ollama response.

    Three layers:
    1. Direct json.loads on the full string
    2. Regex extraction of first {...} block
    3. Degraded fallback with status=parse_error
    """
    # Layer 1: direct parse
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Layer 2: regex extraction
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            pass

    # Layer 3: fallback
    return {"status": "parse_error", "raw": raw_text[:500]}


def write_report(conn: duckdb.DuckDBPyConnection, alert_id: int, report: dict) -> None:
    """Write structured report JSON to alerts.llm_report column."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE alerts SET llm_report=? WHERE id=?",
        [json.dumps(report), alert_id],
    )


async def investigate(
    conn: duckdb.DuckDBPyConnection,
    alert_id: int,
    host: str,
    alert_dict: dict,
) -> None:
    """
    Async coroutine: investigate an alert using Ollama.

    Gathers context from DuckDB, builds a prompt, calls Ollama, parses the JSON
    report, and writes it to alerts.llm_report. Never raises — Ollama unavailability
    writes a degraded record instead.
    """
    try:
        context = gather_context(conn, alert_id, host)
        if not context:
            return

        prompt = build_prompt(context)
        client = ollama.AsyncClient()
        response = await client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format="json",
            options={"temperature": 0.1},
        )
        raw_text = response["message"]["content"]
        report = parse_report(raw_text)
        write_report(conn, alert_id, report)
        log.info(
            "Investigation complete for alert %d: severity=%s",
            alert_id, report.get("severity"),
        )

    except ollama.ResponseError as exc:
        log.warning("Ollama API error for alert %d: %s", alert_id, exc)
        try:
            write_report(conn, alert_id, {"status": "unavailable", "reason": str(exc)})
        except Exception:
            pass

    except Exception as exc:
        log.warning("Investigation failed for alert %d: %s", alert_id, exc)
        try:
            write_report(conn, alert_id, {"status": "unavailable", "reason": str(exc)})
        except Exception:
            pass
