"""DETC-03 — T1571: New listener on unusual port."""
from datetime import datetime, timezone, timedelta

RULE_ID = "unusual_listener"
COOLDOWN_SECONDS = 300
LOOKBACK_SECONDS = 30
# Ports that are normal and should not alert
COMMON_PORTS = [
    22, 80, 443, 631, 3000, 3306, 4000, 5000, 5173, 5432,
    6379, 8000, 8080, 8443, 8888, 9000, 11434, 27017,
]
# macOS ephemeral (dynamic) port range starts at 49152 — ignore all of these
EPHEMERAL_PORT_MIN = 49152


def run(conn, host):
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=LOOKBACK_SECONDS)
        ports_literal = f"({', '.join(str(p) for p in COMMON_PORTS)})"
        cur = conn.cursor()
        cur.execute(
            f"""SELECT id, local_port, local_ip
                FROM events
                WHERE host = ?
                  AND event_type = 'network_conn'
                  AND remote_ip IS NULL
                  AND local_port IS NOT NULL
                  AND local_port NOT IN {ports_literal}
                  AND local_port < {EPHEMERAL_PORT_MIN}
                  AND ts > ?
                LIMIT 10""",
            [host, cutoff]
        )
        rows = cur.fetchall()
        if not rows:
            return None
        dedup_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=COOLDOWN_SECONDS)
        cur2 = conn.cursor()
        cur2.execute("SELECT id FROM alerts WHERE rule_id = ? AND host = ? AND ts > ? LIMIT 1",
                     [RULE_ID, host, dedup_cutoff])
        if cur2.fetchone():
            return None
        event_id, port, local_ip = rows[0]
        return {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "host": host,
            "rule_id": RULE_ID,
            "severity": "high",
            "description": f"Non-standard port listener on {local_ip or '0.0.0.0'}:{port} — possible backdoor or C2 channel",
            "mitre_id": "T1571",
            "related_event_ids": [r[0] for r in rows],
            "llm_report": None,
        }
    except Exception:
        return None
