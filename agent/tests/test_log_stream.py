"""
Unit tests for agent/log_stream.py

Only parse_log_event() is unit-tested here.
start_log_stream() requires a live subprocess and is excluded from unit tests.
"""

from agent.log_stream import parse_log_event


# ---------------------------------------------------------------------------
# Test: full well-formed object
# ---------------------------------------------------------------------------

def test_parse_log_event_returns_auth_event_type():
    """parse_log_event() must always return event_type='auth_event'."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "authentication failure",
        "messageType": "Error",
        "subsystem": "com.apple.authd",
    })
    assert result["event_type"] == "auth_event"


def test_parse_log_event_process_name_from_path():
    """process_name is the last path component of processImagePath."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "authentication failure",
        "messageType": "Error",
        "subsystem": "com.apple.authd",
    })
    assert result["process_name"] == "sudo"


def test_parse_log_event_pid_from_processID():
    """pid is set from processID field."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "auth ok",
        "messageType": "Info",
        "subsystem": "com.apple.authd",
    })
    assert result["pid"] == 1234


def test_parse_log_event_username_from_userID():
    """username is str(userID)."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "auth ok",
        "messageType": "Info",
        "subsystem": "com.apple.authd",
    })
    assert result["username"] == "501"


def test_parse_log_event_cmdline_is_eventMessage():
    """cmdline is set to eventMessage (up to 500 chars)."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "authentication failure",
        "messageType": "Error",
        "subsystem": "com.apple.authd",
    })
    assert result["cmdline"] == "authentication failure"


def test_parse_log_event_raw_json_has_required_keys():
    """raw_json must have keys: subsystem, messageType, eventMessage, processImagePath."""
    result = parse_log_event({
        "processImagePath": "/usr/bin/sudo",
        "processID": 1234,
        "userID": 501,
        "eventMessage": "auth ok",
        "messageType": "Error",
        "subsystem": "com.apple.authd",
    })
    rj = result["raw_json"]
    for key in ("subsystem", "messageType", "eventMessage", "processImagePath"):
        assert key in rj, f"Missing key in raw_json: {key}"


# ---------------------------------------------------------------------------
# Test: missing processImagePath
# ---------------------------------------------------------------------------

def test_parse_log_event_process_name_none_when_key_absent():
    """process_name is None when processImagePath key is absent."""
    result = parse_log_event({
        "processID": 999,
        "userID": 0,
        "eventMessage": "some event",
    })
    assert result["process_name"] is None


def test_parse_log_event_process_name_none_when_empty_string():
    """process_name is None when processImagePath is an empty string."""
    result = parse_log_event({
        "processImagePath": "",
        "processID": 999,
        "userID": 0,
        "eventMessage": "some event",
    })
    assert result["process_name"] is None


# ---------------------------------------------------------------------------
# Test: eventMessage truncation to 500 chars
# ---------------------------------------------------------------------------

def test_parse_log_event_truncates_cmdline_to_500_chars():
    """cmdline must be exactly 500 chars when eventMessage is longer than 500 chars."""
    long_msg = "A" * 600
    result = parse_log_event({
        "processImagePath": "/usr/bin/authd",
        "processID": 1,
        "userID": 0,
        "eventMessage": long_msg,
    })
    assert len(result["cmdline"]) == 500


def test_parse_log_event_truncates_raw_json_eventMessage_to_500_chars():
    """raw_json['eventMessage'] must also be truncated to 500 chars."""
    long_msg = "B" * 700
    result = parse_log_event({
        "processImagePath": "/usr/bin/authd",
        "processID": 1,
        "userID": 0,
        "eventMessage": long_msg,
    })
    assert len(result["raw_json"]["eventMessage"]) == 500


# ---------------------------------------------------------------------------
# Test: empty / missing fields
# ---------------------------------------------------------------------------

def test_parse_log_event_handles_empty_dict_no_exception():
    """parse_log_event({}) must not raise an exception."""
    result = parse_log_event({})
    assert result["event_type"] == "auth_event"
