"""DETC-07 — T1059: Shell spawned by unusual parent process."""
from datetime import datetime, timezone, timedelta

RULE_ID = "shell_unusual_parent"
COOLDOWN_SECONDS = 120
LOOKBACK_SECONDS = 30
SHELLS = ('bash', 'sh', 'zsh', 'fish')
UNUSUAL_PARENTS = ('python', 'python3', 'Python', 'ruby', 'perl', 'node', 'java', 'osascript')


def run(conn, host):
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=LOOKBACK_SECONDS)
        shells_literal = f"({', '.join(repr(s) for s in SHELLS)})"
        parents_literal = f"({', '.join(repr(s) for s in UNUSUAL_PARENTS)})"
        cur = conn.cursor()
        cur.execute(
            f"""SELECT id, process_name, pid, ppid
                FROM events
                WHERE host = ?
                  AND event_type = 'process_start'
                  AND process_name IN {shells_literal}
                  AND ppid IS NOT NULL
                  AND ts > ?
                LIMIT 10""",
            [host, cutoff]
        )
        shell_rows = cur.fetchall()
        for shell_id, shell_name, shell_pid, shell_ppid in shell_rows:
            cur2 = conn.cursor()
            cur2.execute(
                f"SELECT id, process_name FROM events "
                f"WHERE host = ? AND pid = ? AND process_name IN {parents_literal} LIMIT 1",
                [host, shell_ppid]
            )
            parent_row = cur2.fetchone()
            if parent_row:
                dedup_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=COOLDOWN_SECONDS)
                cur3 = conn.cursor()
                cur3.execute("SELECT id FROM alerts WHERE rule_id = ? AND host = ? AND ts > ? LIMIT 1",
                             [RULE_ID, host, dedup_cutoff])
                if cur3.fetchone():
                    return None
                return {
                    "ts": datetime.now(timezone.utc).replace(tzinfo=None),
                    "host": host,
                    "rule_id": RULE_ID,
                    "severity": "high",
                    "description": f"Suspicious shell spawn: {shell_name} launched by {parent_row[1]} (pid={shell_ppid}) — possible code execution",
                    "mitre_id": "T1059",
                    "related_event_ids": [shell_id, parent_row[0]],
                    "llm_report": None,
                }
        return None
    except Exception:
        return None
