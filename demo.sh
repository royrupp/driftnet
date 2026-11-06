#!/usr/bin/env bash
# demo.sh — Driftnet detection demo
#
# Triggers 4 of 5 detection rules with harmless payloads.
# Requires the backend and agent to be running (see start.sh).
# Run from the project root: bash demo.sh
#
# Rules triggered:
#   unusual_listener   T1571     — nc listening on unusual port
#   download_exec      T1059.004 — curl | bash pattern
#   shell_unusual_parent T1059   — bash spawned from Python
#   sudo_bruteforce    T1548.003 — repeated auth failures (requires agent sudo)
#
# Note: download_exec requires the agent to capture the bash -c "..." cmdline,
#       which happens on the next psutil poll cycle (up to 2.5 seconds).
#       sudo_bruteforce requires the macOS log stream (agent running with sudo).

set -e

BASE_URL="http://localhost:8000"

echo "========================================"
echo " Driftnet Detection Demo"
echo "========================================"
echo ""
echo "Backend: $BASE_URL"
echo "Dashboard: http://localhost:5173"
echo ""

# ── Rule 1: unusual_listener (T1571) ─────────────────────────────────────────
echo "[1/4] unusual_listener (T1571): opening nc listener on port 4444..."
nc -l 4444 &
NC_PID=$!
sleep 5
kill $NC_PID 2>/dev/null || true
wait $NC_PID 2>/dev/null || true
echo "      Done. Listening on port 4444 for 5 seconds."
echo ""
sleep 2

# ── Rule 2: download_exec (T1059.004) ────────────────────────────────────────
echo "[2/4] download_exec (T1059.004): running curl | bash against backend..."
# Wrap in bash -c with a trailing sleep so the process stays alive long enough
# for the agent's 2.5s poll cycle to capture the curl|bash cmdline pattern
bash -c "curl -s $BASE_URL/echo.sh | bash; sleep 4" &
CURL_PID=$!
sleep 5
kill $CURL_PID 2>/dev/null || true
wait $CURL_PID 2>/dev/null || true
echo "      Done. Curl-to-bash pattern executed."
echo ""
sleep 2

# ── Rule 3: shell_unusual_parent (T1059) ─────────────────────────────────────
echo "[3/4] shell_unusual_parent (T1059): python3 spawning bash subprocess..."
# Keep python3 alive long enough for the agent to capture it (agent polls every 2.5s)
python3 -c "
import subprocess, time
p = subprocess.Popen(['bash', '-c', 'sleep 8'])
time.sleep(6)
p.terminate()
"
echo "      Done. bash spawned from python3."
echo ""
sleep 2

# ── Rule 4: sudo_bruteforce (T1548.003) ──────────────────────────────────────
echo "[4/4] sudo_bruteforce (T1548.003): generating 5 failed sudo auth events..."
echo "      (requires agent running with sudo for macOS log stream)"
for i in 1 2 3 4 5; do
    # Attempt sudo with a wrong password via stdin; expect failure
    echo "wrongpassword" | sudo -S true 2>/dev/null || true
    sleep 0.3
done
echo "      Done. 5 failed sudo attempts sent."
echo ""

echo "========================================"
echo " Demo complete"
echo "========================================"
echo ""
echo "Open http://localhost:5173 to see alerts in the dashboard."
echo "If Ollama is running, llm_report will populate within ~15 seconds."
echo ""
echo "Or query directly:"
echo "  curl -s $BASE_URL/alerts | python3 -m json.tool | head -60"
echo "  curl -s $BASE_URL/metrics | python3 -m json.tool"
