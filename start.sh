#!/usr/bin/env bash
# start.sh — Start Driftnet backend and frontend together
#
# Usage:
#   bash start.sh           # starts both; Ctrl-C stops both
#
# Backend runs on http://localhost:8000
# Frontend runs on http://localhost:5173
#
# To start the agent in a separate terminal (requires sudo for macOS log stream):
#   sudo python3 agent/agent.py

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "Starting Driftnet..."
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "  [backend]  http://localhost:8000  (pid $BACKEND_PID)"

# Give backend a moment to bind before starting frontend
sleep 1

# ── Frontend ─────────────────────────────────────────────────────────────────
cd "$PROJECT_DIR/frontend"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!
cd "$PROJECT_DIR"
echo "  [frontend] http://localhost:5173  (pid $FRONTEND_PID)"

echo ""
echo "Press Ctrl-C to stop all processes."
echo ""
echo "To start the agent (separate terminal, requires sudo):"
echo "  cd $PROJECT_DIR && sudo python3 agent/agent.py"
echo ""

# Tear down both on Ctrl-C or SIGTERM
_shutdown() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap _shutdown INT TERM

wait
