#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
VITE_API_TARGET="${VITE_API_TARGET:-http://${BACKEND_HOST}:${BACKEND_PORT}}"
UV_CACHE_DIR="${UV_CACHE_DIR:-${ROOT_DIR}/.uv-cache}"
LOG_DIR="${LOG_DIR:-${ROOT_DIR}/logs}"
BACKEND_LOG="${BACKEND_LOG:-${LOG_DIR}/flagforge-backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-${LOG_DIR}/flagforge-frontend.log}"

BACKEND_PID=""
FRONTEND_PID=""
CLEANED_UP=0

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

print_log_tail() {
  local file="$1"
  local name="$2"

  if [[ -f "$file" ]]; then
    echo
    echo "Last log lines from $name ($file):" >&2
    tail -n 40 "$file" >&2 || true
  fi
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local attempts="${3:-40}"
  local pid="${4:-}"
  local log_file="${5:-}"

  for ((i = 1; i <= attempts; i += 1)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    if [[ -n "$pid" ]] && ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "$name exited before it became ready: $url" >&2
      print_log_tail "$log_file" "$name"
      return 1
    fi
    sleep 0.25
  done

  echo "$name did not become ready: $url" >&2
  print_log_tail "$log_file" "$name"
  return 1
}

cleanup() {
  local status=$?

  if [[ "$CLEANED_UP" == "1" ]]; then
    exit "$status"
  fi
  CLEANED_UP=1
  trap - INT TERM EXIT

  if [[ -n "$FRONTEND_PID" ]] || [[ -n "$BACKEND_PID" ]]; then
    echo
    echo "Stopping FlagForge..."
  fi

  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "$FRONTEND_PID" ]]; then
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi

  exit "$status"
}

trap cleanup INT TERM EXIT

require_cmd uv
require_cmd npm
require_cmd curl

mkdir -p "$LOG_DIR"

echo "Starting FlagForge..."
echo "Backend : http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Logs    :"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"

UV_CACHE_DIR="$UV_CACHE_DIR" \
CTF_AGENT_HOST="$BACKEND_HOST" \
CTF_AGENT_PORT="$BACKEND_PORT" \
uv run python -m backend.web.app >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

wait_for_http \
  "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" \
  "Backend" \
  40 \
  "$BACKEND_PID" \
  "$BACKEND_LOG"

VITE_API_TARGET="$VITE_API_TARGET" \
npm --prefix frontend run dev -- \
  --host "$FRONTEND_HOST" \
  --port "$FRONTEND_PORT" \
  --strictPort >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

wait_for_http \
  "http://${FRONTEND_HOST}:${FRONTEND_PORT}" \
  "Frontend" \
  40 \
  "$FRONTEND_PID" \
  "$FRONTEND_LOG"

echo
echo "FlagForge is running."
echo "Open: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Press Ctrl+C to stop both services."

set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
EXITED_STATUS=$?
set -e

echo
echo "One service stopped. Check logs for details:" >&2
echo "  $BACKEND_LOG" >&2
echo "  $FRONTEND_LOG" >&2
exit "$EXITED_STATUS"
