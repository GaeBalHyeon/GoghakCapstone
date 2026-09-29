#!/usr/bin/env bash
set -u

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
EVGUARD_DIR="$(dirname "$AGENT_DIR")"
VENV_DIR="${EVGUARD_VENV:-$EVGUARD_DIR/venv}"
LOG_FILE="${EVGUARD_LOG:-$EVGUARD_DIR/agent.log}"

exec 9>"$EVGUARD_DIR/agent.lock"
if ! flock -n 9; then
  exit 0
fi

cd "$AGENT_DIR"
export PYTHONNOUSERSITE=1

while true; do
  echo "[$(date --iso-8601=seconds)] EV Fire Guard agent starting" >> "$LOG_FILE"
  "$VENV_DIR/bin/python" -u agent.py >> "$LOG_FILE" 2>&1
  exit_code=$?
  echo "[$(date --iso-8601=seconds)] agent stopped (code=$exit_code); retrying in 5 seconds" >> "$LOG_FILE"
  sleep 5
done
