"""DETC-05 — T1059.004: Download-and-execute via curl/wget piped to shell."""
from datetime import datetime, timezone, timedelta

RULE_ID = "download_exec"
COOLDOWN_SECONDS = 120
LOOKBACK_SECONDS = 30


def run(conn, host):
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=LOOKBACK_SECONDS)
        cur = conn.cursor()
        cur.execute(
            """SELECT id, process_name, cmdline
               FROM events
               WHERE host = ?
                 AND event_type = 'process_start'
                 AND cmdline IS NOT NULL
                 AND (
                     cmdline ILIKE '%curl%|%bash%'
                  OR cmdline ILIKE '%curl%|%sh%'
                  OR cmdline ILIKE '%wget%|%bash%'
                  OR cmdline ILIKE '%wget%|%sh%'
                 )
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
        return {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "host": host,
            "rule_id": RULE_ID,
            "severity": "critical",
            "description": f"Download-and-execute: '{rows[0][1]}' ran curl/wget piped to shell",
            "mitre_id": "T1059.004",
            "related_event_ids": [r[0] for r in rows],
            "llm_report": None,
        }
    except Exception:
        return None
