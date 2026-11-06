"""DETC-06 — T1548.003: Repeated failed sudo / auth attempts."""
from datetime import datetime, timezone, timedelta

RULE_ID = "sudo_bruteforce"
COOLDOWN_SECONDS = 120
LOOKBACK_SECONDS = 60
THRESHOLD = 3


def run(conn, host):
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=LOOKBACK_SECONDS)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username
               FROM events
               WHERE host = ?
                 AND event_type = 'auth_event'
                 AND ts > ?
               ORDER BY ts DESC
               LIMIT 10""",
            [host, cutoff]
        )
        rows = cur.fetchall()
        if len(rows) < THRESHOLD:
            return None
        dedup_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=COOLDOWN_SECONDS)
        cur2 = conn.cursor()
        cur2.execute("SELECT id FROM alerts WHERE rule_id = ? AND host = ? AND ts > ? LIMIT 1",
                     [RULE_ID, host, dedup_cutoff])
        if cur2.fetchone():
            return None
        return {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "host": host,
            "rule_id": RULE_ID,
            "severity": "high",
            "description": f"Brute-force detected: {len(rows)} failed sudo/auth attempts in 60 seconds",
            "mitre_id": "T1548.003",
            "related_event_ids": [r[0] for r in rows],
            "llm_report": None,
        }
    except Exception:
        return None
