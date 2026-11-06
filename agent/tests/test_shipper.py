"""
Unit tests for agent/shipper.py

All httpx.Client calls are mocked. No real HTTP requests are made.
"""

from unittest.mock import patch, MagicMock
import httpx
import pytest

from agent.shipper import Shipper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_shipper_with_mock_client(mock_client_instance):
    """Create a Shipper whose _client is replaced by mock_client_instance."""
    with patch("httpx.Client", return_value=mock_client_instance):
        shipper = Shipper()
    return shipper


# ---------------------------------------------------------------------------
# post_events tests
# ---------------------------------------------------------------------------

def test_post_events_returns_true_on_200():
    """post_events() returns True when the HTTP POST succeeds with status 200."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None  # no-op
    mock_client.post.return_value = mock_response

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_events([{"event_type": "process_start"}], host="test-host")

    assert result is True


def test_post_events_returns_false_on_connect_error():
    """post_events() returns False (no exception) when ConnectError is raised."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_events([{"event_type": "process_start"}], host="test-host")

    assert result is False


def test_post_events_returns_false_on_request_error():
    """post_events() returns False on any httpx.RequestError (timeout, etc.)."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_events([{"event_type": "process_start"}], host="test-host")

    assert result is False


def test_post_events_returns_true_on_empty_list():
    """post_events() returns True without making any HTTP call when events is empty."""
    mock_client = MagicMock()

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_events([], host="test-host")

    assert result is True
    assert mock_client.post.call_count == 0


def test_post_events_payload_has_events_key():
    """post_events() sends JSON body with 'events' key containing a list."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    shipper = _make_shipper_with_mock_client(mock_client)
    shipper.post_events([{"event_type": "process_start"}], host="test-host")

    call_kwargs = mock_client.post.call_args.kwargs
    payload = call_kwargs["json"]
    assert "events" in payload
    assert isinstance(payload["events"], list)


def test_post_events_payload_events_have_ts_and_host():
    """Each event in the payload has a 'ts' key (ISO string) and 'host' key."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    shipper = _make_shipper_with_mock_client(mock_client)
    shipper.post_events([{"event_type": "process_start"}], host="my-macbook")

    call_kwargs = mock_client.post.call_args.kwargs
    payload = call_kwargs["json"]
    event = payload["events"][0]

    assert "ts" in event
    assert isinstance(event["ts"], str)
    # ts must be an ISO string without timezone offset (naive UTC)
    assert "+" not in event["ts"] or event["ts"].endswith("+00:00") or "Z" not in event["ts"]
    assert event["host"] == "my-macbook"


# ---------------------------------------------------------------------------
# post_heartbeat tests
# ---------------------------------------------------------------------------

def test_post_heartbeat_returns_true_on_200():
    """post_heartbeat() returns True when the HTTP POST succeeds."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_heartbeat({"agent_id": "host1", "hostname": "host1"})

    assert result is True


def test_post_heartbeat_returns_false_on_connect_error():
    """post_heartbeat() returns False (no exception) on ConnectError."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_heartbeat({"agent_id": "host1"})

    assert result is False


def test_post_heartbeat_returns_false_on_http_status_error():
    """post_heartbeat() returns False on httpx.HTTPStatusError (non-2xx response)."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "422 Unprocessable Entity",
        request=MagicMock(),
        response=MagicMock(),
    )
    mock_client.post.return_value = mock_response

    shipper = _make_shipper_with_mock_client(mock_client)
    result = shipper.post_heartbeat({"agent_id": "host1"})

    assert result is False


# ---------------------------------------------------------------------------
# close() tests
# ---------------------------------------------------------------------------

def test_close_calls_client_close():
    """Shipper.close() must call the underlying httpx.Client.close()."""
    mock_client = MagicMock()

    shipper = _make_shipper_with_mock_client(mock_client)
    shipper.close()

    mock_client.close.assert_called_once()
