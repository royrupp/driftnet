"""BACK-01: FastAPI server starts and serves HTTP."""


def test_health(client):
    """
    BACK-01: GET / returns 200 with {"status": "ok"}.

    This is the most basic check that the server started, the lifespan ran,
    DuckDB connected, and the router is registered. If this fails, nothing else works.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
