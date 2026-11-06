"""
agent/log_stream.py — macOS log stream subprocess parser for auth events.

Provides:
  parse_log_event(obj: dict) -> dict
  start_log_stream(event_queue: queue.Queue) -> subprocess.Popen
"""

import json
import queue
import subprocess
import threading

AUTH_PREDICATE = 'subsystem == "com.apple.authd" OR process == "sudo"'


def parse_log_event(obj: dict) -> dict:
    """
    Parse a single ndjson log object from the macOS log stream into an event dict.

    - processImagePath → process_name (last path component)
    - processID → pid
    - userID → username (as string)
    - eventMessage → cmdline (truncated to 500 chars)
    - raw_json contains: subsystem, messageType, eventMessage, processImagePath

    All fields are optional; missing keys default to None / empty string.
    Satisfies T-02-02: eventMessage truncated to 500 chars (DoS protection).
    """
    path = obj.get('processImagePath', '') or ''
    process_name = path.split('/')[-1] if path else None

    msg = obj.get('eventMessage', '') or ''
    msg = msg[:500]  # T-02-02: truncate to prevent large payload DoS

    user_id = obj.get('userID')
    username = str(user_id) if user_id is not None else None

    return {
        "event_type": "auth_event",
        "process_name": process_name,
        "pid": obj.get('processID'),
        "username": username,
        "cmdline": msg if msg else None,
        "raw_json": {
            "subsystem": obj.get('subsystem'),
            "messageType": obj.get('messageType'),
            "eventMessage": msg,
            "processImagePath": path,
        },
    }


def start_log_stream(event_queue: queue.Queue) -> subprocess.Popen:
    """
    Launch the macOS `log stream` subprocess for auth/sudo events.

    Reads ndjson lines in a daemon thread and puts parsed objects into event_queue.
    Returns the Popen handle so the caller can call proc.terminate() on shutdown.

    Requires: macOS, sudo (for full log access)
    Satisfies: AGNT-03, T-02-01 (AUTH_PREDICATE is a module-level constant, never interpolated)
    """
    proc = subprocess.Popen(
        ['log', 'stream',
         '--predicate', AUTH_PREDICATE,
         '--style', 'ndjson',
         '--level', 'info'],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,  # line-buffered — flush each line as it arrives
    )

    def _reader():
        for raw in proc.stdout:
            raw = raw.strip()
            if not raw.startswith('{'):
                continue  # skip the "Filtering the log data using..." header line
            try:
                obj = json.loads(raw)
                event_queue.put(obj)
            except json.JSONDecodeError:
                pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return proc
