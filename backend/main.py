"""
backend/main.py — FastAPI application factory and entry point.

Single-writer design: this process is the only code that opens driftnet.duckdb.
The agent and frontend communicate only via REST and WebSocket.
DuckDB is embedded (no separate DB server) — it lives inside this process.

Architecture:
  Agent --POST /events--> Backend --DuckDB--> Detection loop (Phase 3)
  Browser --GET /events, GET /alerts--> Backend
  Browser <--WebSocket /ws-- Backend (push on new events/alerts/heartbeats)

Run with: uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import duckdb
from fastapi import FastAPI

from backend.db import DB_PATH, init_schema

log = logging.getLogger("driftnet.detection_loop")


async def detection_loop(app: FastAPI) -> None:
    """
    Background detection loop — runs for the lifetime of the application.

    Phase 3 replaces the sleep with actual rule execution:
        await run_detection_rules(app.state.db, manager)
    Having this stub in Phase 1 means Phase 3 does not need to refactor the lifespan —
    it only needs to replace the body of this function.
    """
    from backend.detection.engine import run_detection_cycle
    while True:
        await asyncio.sleep(5)
        try:
            await run_detection_cycle(app.state.db)
        except Exception as exc:
            log.warning("Detection cycle error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager — runs startup before yield, shutdown after yield.

    Startup:
      1. Open DuckDB connection (single writer for the process lifetime)
      2. Run schema DDL (CREATE TABLE IF NOT EXISTS — idempotent)
      3. Launch detection loop as a background task

    Shutdown:
      1. Cancel and await detection task (CancelledError is expected — not an error)
      2. Close DuckDB connection
    """
    # Startup
    app.state.db = duckdb.connect(app.state.db_path)
    init_schema(app.state.db)
    app.state.detection_task = asyncio.create_task(detection_loop(app))

    yield

    # Shutdown
    app.state.detection_task.cancel()
    try:
        await app.state.detection_task
    except asyncio.CancelledError:
        pass  # Expected on graceful shutdown; not an error.
    app.state.db.close()


def create_app(db_path: str = DB_PATH) -> FastAPI:
    """
    Application factory. Creates and returns a configured FastAPI instance.

    Parameters
    ----------
    db_path : str
        Path to the DuckDB database file. Defaults to DB_PATH ("driftnet.duckdb").
        Tests pass ":memory:" here to get a fresh isolated database per test function.

    Usage
    -----
    Production (via uvicorn):  `app = create_app()`  — module level, see below
    Tests (via conftest.py):   `app = create_app(db_path=":memory:")`
    """
    app = FastAPI(lifespan=lifespan, title="Driftnet")

    # Store db_path before lifespan runs so the lifespan can read it.
    app.state.db_path = db_path

    # Lazy import — router.py is created after main.py in the wave order.
    # Importing inside the function means Wave 1's verify step (which only
    # checks "from backend.main import create_app" without calling it) succeeds
    # before router.py exists. The router is wired when create_app() is called,
    # which happens in Wave 3 when tests run (by which point router.py exists).
    from backend.router import router  # noqa: PLC0415
    app.include_router(router)

    return app


# Production instance — imported by uvicorn as "backend.main:app".
# This is the only duckdb.connect() call in the codebase (BACK-09: single writer).
app = create_app()

# Run with: uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
