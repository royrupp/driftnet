"""
backend/tests/test_investigator.py — Unit tests for the LLM investigator.

All tests use in-memory DuckDB with init_schema applied. No live Ollama required.
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import duckdb

from backend.db import init_schema


def make_conn():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    return conn


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _insert_alert(conn, ts=None, host="testhost"):
    ts = ts or _now()
    conn.execute(
        "INSERT INTO alerts VALUES (nextval('alert_seq'), ?, ?, ?, ?, ?, ?, ?, ?)",
        [ts, host, "unusual_listener", "high", "Unusual port", "T1571", "[]", None],
    )
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM alerts")
    return cur.fetchone()[0]


def _insert_event(conn, ts=None, host="testhost"):
    ts = ts or _now()
    conn.execute(
        "INSERT INTO events VALUES (nextval('event_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [ts, host, "network", "nc", 1234, None, "user", "nc -l 4444",
         "0.0.0.0", 4444, None, None, None],
    )
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM events")
    return cur.fetchone()[0]


class TestGatherContext:
    def test_gather_context_returns_alert_and_events(self):
        from backend.investigator import gather_context
        conn = make_conn()
        ts = _now()
        alert_id = _insert_alert(conn, ts=ts)
        _insert_event(conn, ts=ts)
        _insert_event(conn, ts=ts + timedelta(seconds=30))
        _insert_event(conn, ts=ts - timedelta(seconds=30))
        result = gather_context(conn, alert_id, "testhost")
        assert result["alert"]["id"] == alert_id
        assert len(result["events"]) == 3

    def test_gather_context_empty_on_missing_alert(self):
        from backend.investigator import gather_context
        conn = make_conn()
        result = gather_context(conn, 9999, "testhost")
        assert result == {}

    def test_gather_context_excludes_out_of_window_events(self):
        from backend.investigator import gather_context
        conn = make_conn()
        ts = _now()
        alert_id = _insert_alert(conn, ts=ts)
        _insert_event(conn, ts=ts - timedelta(minutes=5))  # outside ±2 min window
        _insert_event(conn, ts=ts - timedelta(minutes=1))  # inside window
        result = gather_context(conn, alert_id, "testhost")
        assert len(result["events"]) == 1


class TestBuildPrompt:
    def test_build_prompt_includes_alert_fields(self):
        from backend.investigator import build_prompt
        context = {
            "alert": {
                "rule_id": "unusual_listener",
                "severity": "high",
                "mitre_id": "T1571",
                "description": "Unusual port",
                "host": "h",
                "ts": "2026-11-04T10:00:00",
            },
            "events": [],
        }
        prompt = build_prompt(context)
        assert "unusual_listener" in prompt
        assert "high" in prompt
        assert "T1571" in prompt


class TestParseReport:
    def test_parse_report_valid_json(self):
        from backend.investigator import parse_report
        result = parse_report('{"summary":"test","techniques":[]}')
        assert result["summary"] == "test"

    def test_parse_report_json_embedded_in_text(self):
        from backend.investigator import parse_report
        result = parse_report('Here is the result: {"summary":"embedded"} done')
        assert result["summary"] == "embedded"

    def test_parse_report_fallback_on_garbage(self):
        from backend.investigator import parse_report
        result = parse_report("not json at all")
        assert result["status"] == "parse_error"


class TestWriteReport:
    def test_write_report_updates_llm_report(self):
        from backend.investigator import write_report
        conn = make_conn()
        alert_id = _insert_alert(conn)
        write_report(conn, alert_id, {"summary": "x"})
        cur = conn.cursor()
        cur.execute("SELECT llm_report FROM alerts WHERE id=?", [alert_id])
        raw = cur.fetchone()[0]
        assert json.loads(raw) == {"summary": "x"}


class TestInvestigate:
    def test_investigate_graceful_on_ollama_unavailable(self):
        from backend.investigator import investigate
        conn = make_conn()
        alert_id = _insert_alert(conn)
        _insert_event(conn)
        with patch("backend.investigator.ollama.AsyncClient") as mock_cls:
            instance = mock_cls.return_value
            instance.chat = AsyncMock(side_effect=Exception("connection refused"))
            asyncio.run(investigate(conn, alert_id, "testhost", {}))
        cur = conn.cursor()
        cur.execute("SELECT llm_report FROM alerts WHERE id=?", [alert_id])
        raw = cur.fetchone()[0]
        assert json.loads(raw)["status"] == "unavailable"

    def test_investigate_stores_valid_report(self):
        from backend.investigator import investigate
        conn = make_conn()
        alert_id = _insert_alert(conn)
        _insert_event(conn)
        mock_response = {
            "message": {
                "content": '{"summary":"ok","timeline":[],"severity":"low","techniques":[],"next_steps":[]}'
            }
        }
        with patch("backend.investigator.ollama.AsyncClient") as mock_cls:
            instance = mock_cls.return_value
            instance.chat = AsyncMock(return_value=mock_response)
            asyncio.run(investigate(conn, alert_id, "testhost", {}))
        cur = conn.cursor()
        cur.execute("SELECT llm_report FROM alerts WHERE id=?", [alert_id])
        raw = cur.fetchone()[0]
        assert json.loads(raw)["summary"] == "ok"
