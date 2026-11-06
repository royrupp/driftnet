"""
backend/models.py — Pydantic data contracts for Driftnet.

Every endpoint and test imports types from here. Using Pydantic v2 (installed: 2.12.5).
Having all schemas in one file makes it easy to explain the data model in an interview:
"Here are all the shapes that flow through the system."
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    """
    Alert severity levels. Inheriting str ensures the enum VALUE appears in JSON
    ("critical" not "Severity.critical") — important for the dashboard switch statement.
    """
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


# ---- Ingest models ----

class EventIn(BaseModel):
    """
    Single security event from the agent.
    The agent sends these in batches via POST /events.
    Fields are all optional except the three required identifiers (ts, host, event_type)
    because different event types use different fields:
      - process_start: process_name, pid, ppid, cmdline
      - network_conn:  local_ip/port, remote_ip/port
      - auth_event:    username
    raw_json holds the full original event for future use.
    """
    ts: datetime
    host: str
    event_type: Literal["process_start", "network_conn", "auth_event"]
    process_name: Optional[str] = None
    pid: Optional[int] = None
    ppid: Optional[int] = None
    username: Optional[str] = None
    cmdline: Optional[str] = None
    local_ip: Optional[str] = None
    local_port: Optional[int] = None
    remote_ip: Optional[str] = None
    remote_port: Optional[int] = None
    raw_json: Optional[dict] = None


class EventBatch(BaseModel):
    """Body of POST /events. Agent sends multiple events per flush (every 2-3 seconds)."""
    events: list[EventIn]


class HeartbeatIn(BaseModel):
    """
    Body of POST /heartbeat. Agent sends this every 5 seconds.
    Used to track which agents are alive and their resource usage.
    """
    agent_id: str
    hostname: str
    os_version: str
    agent_version: str
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None


# ---- Response models ----

class EventOut(BaseModel):
    """
    Single event returned by GET /events.
    Same fields as EventIn plus the auto-assigned database id.
    raw_json is Optional[Any] — not Optional[dict] — because DuckDB returns JSON
    columns as strings, not parsed dicts. Pydantic's Any accepts both str and dict.
    """
    id: int
    ts: datetime
    host: str
    event_type: str
    process_name: Optional[str] = None
    pid: Optional[int] = None
    ppid: Optional[int] = None
    username: Optional[str] = None
    cmdline: Optional[str] = None
    local_ip: Optional[str] = None
    local_port: Optional[int] = None
    remote_ip: Optional[str] = None
    remote_port: Optional[int] = None
    raw_json: Optional[Any] = None  # str from DuckDB JSON column


class AlertOut(BaseModel):
    """
    Alert returned by GET /alerts and GET /alerts/{id}.
    related_event_ids and llm_report are stored as JSON strings in DuckDB;
    the response model deserializes them so callers receive native types.
    llm_report is null in Phase 1 — Phase 5 populates it via Ollama.
    """
    id: int
    ts: datetime
    host: str
    rule_id: str
    severity: Severity
    description: Optional[str] = None
    mitre_id: Optional[str] = None
    related_event_ids: list[int] = Field(default_factory=list)
    llm_report: Optional[Any] = None  # None in Phase 1; populated in Phase 5


class AgentStatus(BaseModel):
    """
    Agent status returned on heartbeat response and WebSocket push.
    is_connected is computed at query time (not stored): True if last_seen
    was within the last 15 seconds. This keeps the agents table simple
    while still giving the dashboard a live connection indicator.
    """
    agent_id: str
    hostname: str
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    last_seen: datetime
    is_connected: bool  # True if last_seen within last 15 seconds
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
