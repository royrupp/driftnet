# Driftnet

> Local macOS endpoint detection & response — real-time alerts, MITRE ATT&CK mapping, and on-device LLM investigation. No cloud required.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![DuckDB](https://img.shields.io/badge/DuckDB-embedded-FCD34D)
![Ollama](https://img.shields.io/badge/Ollama-llama3.1-black)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Driftnet watches your Mac for suspicious activity. A lightweight Python agent collects process, network, and auth telemetry every few seconds and ships it to a local backend. Five detection rules mapped to MITRE ATT&CK fire alerts when something looks off. When an alert fires, an on-device LLM (via Ollama) automatically investigates it — gathering context, assessing severity, and suggesting remediation steps — all without sending a byte of data off your machine.

```
  macOS Host
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  Agent (psutil + log stream)                                     │
  │  ├─ process diff every 2.5s  ─────────────────────────────────► │
  │  ├─ network conn diff         POST /events                       │
  │  └─ auth events (sudo/ssh)   ─────────────────────────────────► │
  │                                                                  │
  │  Backend (FastAPI + DuckDB)                                      │
  │  ├─ events table                                                 │
  │  ├─ detection loop (5s)  ──► 5 MITRE rules  ──► alerts table    │
  │  ├─ WebSocket /ws  ──► live push to dashboard                   │
  │  └─ investigator  ──► Ollama (local LLM)  ──► llm_report        │
  │                                                                  │
  │  Dashboard (React + Vite)                                        │
  │  ├─ AgentCard (live status)                                      │
  │  ├─ AlertsPanel (severity badges, MITRE IDs)                    │
  │  ├─ AlertDetail modal (AI report)                                │
  │  └─ EventFeed + EventChart (live scrolling)                     │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
```

## Features

- **5 live detection rules** — reverse shells, download-exec chains, unusual listeners, sudo brute-force, shell-from-interpreter spawning
- **MITRE ATT&CK IDs** on every alert
- **LLM investigation** — each alert gets a structured AI report (summary, timeline, severity, techniques, next steps) generated locally by Ollama within ~15 seconds
- **Graceful degradation** — if Ollama isn't running, detection keeps working; `llm_report` records `{status: unavailable}`
- **Real-time WebSocket dashboard** — dark-mode React UI, live event chart, severity badges
- **Fully local** — no accounts, no API keys, no data leaves the machine
- **Configurable model** — swap the LLM via `OLLAMA_MODEL` env var

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | `python3 --version` |
| Node.js 18+ | `node --version` |
| macOS | Agent uses `log stream` for auth events |
| sudo access | Required for the agent |
| [Ollama](https://ollama.com/download) | Optional — for LLM investigations |

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/zivbeh/driftnet.git
cd driftnet

# 2. Install backend deps
pip install -r requirements.txt

# 3. Install frontend deps
cd frontend && npm install && cd ..

# 4. [Optional] Pull the LLM model
ollama pull llama3.1

# 5. Start backend + frontend
bash start.sh

# 6. Start the agent (new terminal, sudo required)
sudo python3 agent/agent.py
```

Dashboard: **http://localhost:5173**

---

## Demo

With backend and agent running, trigger every detection rule with safe payloads:

```bash
bash demo.sh
```

Watch all five alert types appear in the dashboard within seconds.

---

## Detection rules

| Rule | MITRE | Severity | Triggers on |
|------|-------|----------|-------------|
| `unusual_listener` | T1571 | High | Process binding to unusual port (not 80/443/22/8080) |
| `reverse_shell` | T1059.004 | Critical | Outbound connection to low-numbered port from non-browser |
| `download_exec` | T1059.004 | Critical | `curl \| bash` or `wget \| sh` command pattern |
| `sudo_bruteforce` | T1548.003 | High | 3+ failed sudo/auth events within 60 seconds |
| `shell_unusual_parent` | T1059 | High | bash/zsh/sh spawned by python, ruby, node, perl, java |

---

## LLM investigations

When an alert fires, Driftnet:
1. Queries DuckDB for events on the same host in a **±2 minute window**
2. Builds a structured prompt with alert metadata and event context
3. Calls **Ollama locally** (zero network egress)
4. Parses the JSON response into `summary`, `timeline`, `severity`, `techniques`, `next_steps`
5. Writes the report to `alerts.llm_report` — the dashboard modal renders it when ready

```bash
# Default model
ollama pull llama3.1

# Override model
OLLAMA_MODEL=qwen2.5 bash start.sh
```

If Ollama is not running, `llm_report` is set to `{"status": "unavailable", "reason": "..."}` — detection is never blocked.

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /alerts` | All alerts with llm_report |
| `GET /events` | Recent telemetry events |
| `GET /metrics` | Events/min, alert latency, agent CPU/memory |
| `WS /ws` | Real-time alert and event stream |

```bash
curl http://localhost:8000/metrics | python3 -m json.tool
```

---

## Adding a detection rule

1. Create `backend/detection/rules/my_rule.py`:

```python
"""DETC-XX — TXXXX: Description."""
from datetime import datetime, timezone, timedelta

RULE_ID = "my_rule"
COOLDOWN_SECONDS = 120
LOOKBACK_SECONDS = 30

def run(conn, host):
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=LOOKBACK_SECONDS)
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM events WHERE host=? AND event_type=? AND ts>? LIMIT 10",
            [host, "process_start", cutoff]
        )
        rows = cur.fetchall()
        if not rows:
            return None
        # Dedup: skip if same rule fired recently
        dedup_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=COOLDOWN_SECONDS)
        cur2 = conn.cursor()
        cur2.execute("SELECT id FROM alerts WHERE rule_id=? AND host=? AND ts>? LIMIT 1",
                     [RULE_ID, host, dedup_cutoff])
        if cur2.fetchone():
            return None
        return {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "host": host,
            "rule_id": RULE_ID,
            "severity": "high",
            "description": "My rule fired",
            "mitre_id": "TXXXX",
            "related_event_ids": [r[0] for r in rows],
        }
    except Exception:
        return None
```

2. Import it in `backend/detection/engine.py`:

```python
from backend.detection.rules import my_rule
RULES = [..., my_rule]
```

3. Add a test in `backend/tests/test_detection.py` following the existing pattern.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, DuckDB (embedded), uvicorn |
| Agent | Python, psutil, macOS `log stream` |
| Frontend | React 18, TypeScript, Vite, recharts, WebSocket |
| LLM | Ollama (llama3.1 / qwen2.5), fully local |
| Testing | pytest, pytest-asyncio, unittest.mock |

---

## License

MIT
