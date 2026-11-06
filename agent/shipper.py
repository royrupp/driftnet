"""
agent/shipper.py — httpx sync batch poster and heartbeat poster.

Provides:
  Shipper class with post_events(), post_heartbeat(), close()

All network errors are caught and returned as False — the agent never crashes
due to backend unavailability. Satisfies AGNT-05, AGNT-06, T-02-04.
"""

from datetime import datetime, timezone

import httpx

BACKEND_URL = "http://localhost:8000"
AGENT_VERSION = "0.1.0"


class Shipper:
    """
    Thin HTTP client for posting events and heartbeats to the Driftnet backend.

    Uses a persistent httpx.Client for connection reuse.
    All methods return True on success, False on any network/HTTP error.
    """

    def __init__(self, base_url: str = BACKEND_URL):
        self._client = httpx.Client(base_url=base_url, timeout=5.0)

    def post_events(self, events: list, host: str) -> bool:
        """
        POST a batch of events to /events.

        Returns True if successful or if events is empty.
        Returns False on any httpx.RequestError or httpx.HTTPStatusError.

        ts is a naive UTC ISO string (no timezone offset) as required by the backend.
        Satisfies: AGNT-05, T-02-04 (flush-and-drop strategy).
        """
        if not events:
            return True  # nothing to send — not an error

        ts_now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        payload = {
            "events": [
                {
                    **e,
                    "ts": ts_now,
                    "host": host,
                }
                for e in events
            ]
        }

        try:
            resp = self._client.post("/events", json=payload)
            resp.raise_for_status()
            return True
        except httpx.RequestError:
            return False  # ConnectError, TimeoutException, etc. — backend not up yet
        except httpx.HTTPStatusError:
            return False  # 4xx/5xx from backend — log but don't crash

    def post_heartbeat(self, payload: dict) -> bool:
        """
        POST a heartbeat payload to /heartbeat.

        Returns True on success, False on any RequestError or HTTPStatusError.
        Satisfies: AGNT-06.
        """
        try:
            resp = self._client.post("/heartbeat", json=payload)
            resp.raise_for_status()
            return True
        except (httpx.RequestError, httpx.HTTPStatusError):
            return False

    def close(self):
        """Close the underlying httpx.Client and release connection resources."""
        self._client.close()
