# Suppress the Starlette deprecation warning BEFORE any other imports.
# FastAPI 0.162.0 / Starlette 1.10.0 emits StarletteDeprecationWarning when TestClient
# is imported, suggesting to install httpx2. The httpx2 package is flagged [SUS] by
# slopcheck (possible typosquat of httpx). httpx still works fully; suppress the warning.
import warnings
warnings.filterwarnings("ignore", message=".*httpx2.*")
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")

# Now import starlette to get the warning class — the warnings above will suppress it
try:
    from starlette.testclient import StarletteDeprecationWarning
    warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
except Exception:
    pass

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client():
    """
    TestClient with an in-memory DuckDB database.

    Using :memory: gives each test function a fresh DuckDB instance with no data.
    This prevents test order dependency — each test starts from a clean slate.

    The with-block ensures the lifespan runs (startup + shutdown), so app.state.db
    is initialized and the schema is created before tests run.
    """
    app = create_app(db_path=":memory:")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_event():
    """
    Minimal valid event payload dict for POST /events tests.
    Uses process_start type with the required fields.
    """
    return {
        "events": [
            {
                "ts": "2026-11-04T10:00:00",
                "host": "test-host",
                "event_type": "process_start",
                "process_name": "bash",
                "pid": 1234,
                "ppid": 1,
                "username": "testuser",
                "cmdline": "bash -i",
            }
        ]
    }
