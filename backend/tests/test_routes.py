"""BACK-03 through BACK-07: REST endpoint integration tests."""


def test_post_events(client, sample_event):
    """BACK-03: POST /events with a single valid event returns {"ingested": 1}."""
    response = client.post("/events", json=sample_event)
    assert response.status_code == 200
    assert response.json() == {"ingested": 1}


def test_post_events_multiple(client):
    """BACK-03: POST /events with a batch of 3 events returns {"ingested": 3}."""
    batch = {
        "events": [
            {
                "ts": "2026-11-04T10:00:00",
                "host": "test-host",
                "event_type": "process_start",
                "process_name": "bash",
                "pid": 1234,
                "ppid": 1,
            },
            {
                "ts": "2026-11-04T10:00:01",
                "host": "test-host",
                "event_type": "network_conn",
                "remote_ip": "10.0.0.1",
                "remote_port": 443,
            },
            {
                "ts": "2026-11-04T10:00:02",
                "host": "test-host",
                "event_type": "auth_event",
                "username": "alice",
            },
        ]
    }
    response = client.post("/events", json=batch)
    assert response.status_code == 200
    assert response.json() == {"ingested": 3}


def test_heartbeat_upsert(client):
    """
    BACK-04: Two POST /heartbeat calls with the same agent_id result in an update,
    not a duplicate row (no primary key violation / 500 error).

    The critical assertion: the second heartbeat returns {"status": "ok"} (not 500),
    proving the upsert works. A naive INSERT without ON CONFLICT would raise a
    PK violation on the second call.
    """
    hb = {
        "agent_id": "test-agent-1",
        "hostname": "macbook-test",
        "os_version": "macOS 14.5",
        "agent_version": "0.1.0",
        "cpu_percent": 1.2,
        "memory_mb": 42.0,
    }
    response1 = client.post("/heartbeat", json=hb)
    assert response1.status_code == 200
    assert response1.json() == {"status": "ok"}

    # Second heartbeat with same agent_id — must update, not fail.
    response2 = client.post("/heartbeat", json={**hb, "cpu_percent": 2.5})
    assert response2.status_code == 200
    assert response2.json() == {"status": "ok"}

    # Verify heartbeat does not pollute the events table.
    events_response = client.get("/events")
    assert events_response.status_code == 200
    assert events_response.json() == {"events": []}


def test_get_events_empty(client):
    """BACK-05: GET /events on an empty database returns {"events": []}."""
    response = client.get("/events")
    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_get_events_returns_data(client, sample_event):
    """BACK-05: After POST /events, GET /events returns the ingested event."""
    client.post("/events", json=sample_event)

    response = client.get("/events")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert len(data["events"]) >= 1
    assert data["events"][0]["host"] == "test-host"


def test_get_events_filter_host(client):
    """
    BACK-05: GET /events?host=host-a returns only events from host-a.

    Posts events from two different hosts, then verifies the filter works.
    This covers the host branch of the dynamic WHERE builder in GET /events.
    """
    batch_a = {
        "events": [{"ts": "2026-11-04T10:00:00", "host": "host-a", "event_type": "process_start"}]
    }
    batch_b = {
        "events": [{"ts": "2026-11-04T10:00:01", "host": "host-b", "event_type": "process_start"}]
    }
    client.post("/events", json=batch_a)
    client.post("/events", json=batch_b)

    response = client.get("/events?host=host-a")
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) >= 1
    assert all(e["host"] == "host-a" for e in events)


def test_get_events_filter_event_type(client):
    """
    BACK-05: GET /events?event_type=process_start returns only process_start events.

    Posts events of two different types, then verifies the filter works.
    This covers the event_type branch of the dynamic WHERE builder in GET /events.
    """
    batch_process = {
        "events": [
            {
                "ts": "2026-11-04T10:00:00",
                "host": "filter-host",
                "event_type": "process_start",
                "process_name": "bash",
            }
        ]
    }
    batch_network = {
        "events": [
            {
                "ts": "2026-11-04T10:00:01",
                "host": "filter-host",
                "event_type": "network_conn",
                "remote_ip": "1.2.3.4",
                "remote_port": 80,
            }
        ]
    }
    client.post("/events", json=batch_process)
    client.post("/events", json=batch_network)

    response = client.get("/events?event_type=process_start")
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) >= 1
    assert all(e["event_type"] == "process_start" for e in events)


def test_get_alerts_empty(client):
    """BACK-06: GET /alerts on an empty database returns {"alerts": []}."""
    response = client.get("/alerts")
    assert response.status_code == 200
    assert response.json() == {"alerts": []}


def test_alert_detail_404(client):
    """BACK-07: GET /alerts/{id} returns 404 when the alert does not exist."""
    response = client.get("/alerts/99999")
    assert response.status_code == 404
