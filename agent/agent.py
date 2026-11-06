"""
agent/agent.py — Driftnet endpoint agent main loop.

Entry point: sudo python agent/agent.py

Collects process, network, and auth telemetry via psutil and the macOS log
subsystem, diffs state between poll cycles, and ships batches to the FastAPI
backend at localhost:8000.

Design decisions:
  - stop_event.wait(N) in heartbeat_loop instead of time.sleep(N): instant
    wakeup on shutdown signal (no up-to-5-second hang).
  - queue.Queue(maxsize=1000): bounded queue prevents memory growth if the
    main loop falls behind the log stream reader thread.
  - log_proc.poll() restart: detects subprocess death and restarts so auth
    events are never silently lost (Pitfall 6 from RESEARCH.md).
  - Flush-and-drop on shipper failure: each cycle ships or discards. No
    accumulating backlog when the backend is unreachable. (T-02-04)
"""

import logging
import os
import platform
import queue
import signal
import socket
import sys
import threading
import time

# Allow `sudo python3 agent/agent.py` from the project root — add the project
# root to sys.path so `from agent.collector import ...` resolves correctly even
# when the script is invoked as a file rather than as `python3 -m agent.agent`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil

from agent.collector import (
    diff_connections,
    diff_processes,
    snapshot_connections,
    snapshot_processes,
)
from agent.log_stream import parse_log_event, start_log_stream
from agent.shipper import Shipper

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

AGENT_VERSION = "0.1.0"
POLL_INTERVAL = 2.5      # seconds — AGNT-05: batch every 2–3 seconds
HEARTBEAT_INTERVAL = 5   # seconds — AGNT-06

AGENT_ID = socket.gethostname()

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("driftnet.agent")


# ---------------------------------------------------------------------------
# Heartbeat daemon thread
# ---------------------------------------------------------------------------

def heartbeat_loop(shipper: Shipper, stop_event: threading.Event):
    """
    Post a heartbeat to the backend every HEARTBEAT_INTERVAL seconds.

    Uses stop_event.wait() instead of time.sleep() so shutdown is immediate.
    Satisfies: AGNT-06.
    """
    while not stop_event.is_set():
        payload = {
            "agent_id": AGENT_ID,
            "hostname": socket.gethostname(),
            "os_version": f"macOS {platform.mac_ver()[0]}",
            "agent_version": AGENT_VERSION,
            "cpu_percent": psutil.cpu_percent(interval=None),   # non-blocking after primer
            "memory_mb": psutil.Process().memory_info().rss / 1024 / 1024,
        }
        ok = shipper.post_heartbeat(payload)
        if not ok:
            log.warning("Heartbeat POST failed — backend may be starting up")
        stop_event.wait(HEARTBEAT_INTERVAL)   # interruptible sleep


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    log.info(f"Driftnet agent {AGENT_VERSION} starting on {AGENT_ID}")

    # Prime CPU percent cache (must call once before non-blocking reads)
    psutil.cpu_percent(interval=0.1)

    # Initialize components
    shipper = Shipper()
    log_queue: queue.Queue = queue.Queue(maxsize=1000)
    stop_event = threading.Event()

    # Start macOS log stream subprocess (auth/sudo events)
    log_proc = start_log_stream(log_queue)
    log.info("log stream subprocess started (auth/sudo events)")

    # Start heartbeat daemon thread
    hb_thread = threading.Thread(
        target=heartbeat_loop,
        args=(shipper, stop_event),
        daemon=True,
        name="heartbeat",
    )
    hb_thread.start()
    log.info(f"Heartbeat thread started (interval={HEARTBEAT_INTERVAL}s)")

    # Register signal handlers for clean shutdown
    def _shutdown(signum, frame):
        log.info("Shutdown signal received — stopping agent")
        stop_event.set()
        log_proc.terminate()
        shipper.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)   # Ctrl-C

    # State for diffing between poll cycles
    prev_procs: dict = {}
    prev_conns: dict = {}

    log.info(f"Polling every {POLL_INTERVAL}s — posting to http://localhost:8000")

    try:
        while True:
            events = []

            # --- Process diff (AGNT-01, AGNT-04) ---
            curr_procs = snapshot_processes()
            new_proc_events = diff_processes(prev_procs, curr_procs)
            events.extend(new_proc_events)
            prev_procs = curr_procs
            if new_proc_events:
                log.debug(f"{len(new_proc_events)} new process event(s)")

            # --- Network diff (AGNT-02, AGNT-04) ---
            # snapshot_connections() returns {} gracefully if AccessDenied (non-sudo)
            curr_conns = snapshot_connections()
            new_conn_events = diff_connections(prev_conns, curr_conns)
            events.extend(new_conn_events)
            prev_conns = curr_conns
            if new_conn_events:
                log.debug(f"{len(new_conn_events)} new connection event(s)")

            # --- Auth event drain (AGNT-03) ---
            # get_nowait() is non-blocking; drain everything the reader thread queued
            drained = 0
            while True:
                try:
                    obj = log_queue.get_nowait()
                    events.append(parse_log_event(obj))
                    drained += 1
                except queue.Empty:
                    break
            if drained:
                log.debug(f"{drained} auth event(s) from log stream")

            # --- Ship batch (AGNT-05) ---
            # T-02-04: flush-and-drop — never accumulate a backlog
            if events:
                ok = shipper.post_events(events, host=AGENT_ID)
                if ok:
                    log.info(f"Shipped {len(events)} event(s)")
                else:
                    log.warning(
                        f"POST /events failed — dropping {len(events)} event(s) this cycle"
                    )

            # Restart log stream subprocess if it died (T-02-05)
            if log_proc.poll() is not None:
                log.warning("log stream subprocess exited — restarting")
                log_proc = start_log_stream(log_queue)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        # Fallback if signal handler did not fire (e.g., running without sudo signals)
        log.info("KeyboardInterrupt — shutting down")
        stop_event.set()
        log_proc.terminate()
        shipper.close()


if __name__ == "__main__":
    main()
