"""DETC-04 — T1059.004: Reverse shell command patterns."""
from datetime import datetime, timezone, timedelta

RULE_ID = "reverse_shell"
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
                     cmdline ILIKE '%bash -i%'
                  OR cmdline ILIKE '%/dev/tcp/%'
                  OR cmdline ILIKE '% -e /bin/bash%'
                  OR cmdline ILIKE '% -e /bin/sh%'
                  OR cmdline ILIKE '%ncat%'
                  OR cmdline ILIKE '%mkfifo%'
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
        event_id, proc_name, cmdline = rows[0]
        return {
            "ts": datetime.now(timezone.utc).replace(tzinfo=None),
            "host": host,
            "rule_id": RULE_ID,
            "severity": "critical",
            "description": f"Reverse shell attempt by '{proc_name}': {(cmdline or '')[:80]}",
            "mitre_id": "T1059.004",
            "related_event_ids": [r[0] for r in rows],
            "llm_report": None,
        }
    except Exception:
        return None
