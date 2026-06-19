#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_HOST="${HELLOBEAUTY_API_HOST:-127.0.0.1}"
WEB_HOST="${HELLOBEAUTY_WEB_HOST:-127.0.0.1}"
REQUESTED_API_PORT="${HELLOBEAUTY_API_PORT:-7860}"
REQUESTED_WEB_PORT="${HELLOBEAUTY_WEB_PORT:-3000}"
START_WEB="${HELLOBEAUTY_START_WEB:-1}"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "Missing backend dependencies. Install them first, or run from the checked-in .venv." >&2
  exit 1
fi

validate_port() {
  local port="$1"
  local label="$2"
  if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
    echo "${label} port must be an integer between 1 and 65535; got '${port}'." >&2
    exit 1
  fi
}

is_port_free() {
  "$PYTHON_BIN" - "$1" "$2" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
}

choose_port() {
  local host="$1"
  local requested_port="$2"
  local label="$3"
  local env_name="$4"
  local port="$requested_port"
  local max_port=$((requested_port + 49))

  if ((max_port > 65535)); then
    max_port=65535
  fi

  if [[ -n "${!env_name:-}" ]]; then
    if is_port_free "$host" "$port"; then
      echo "$port"
      return
    fi
    echo "${env_name}=${port} is already in use." >&2
    exit 1
  fi

  while ((port <= max_port)); do
    if is_port_free "$host" "$port"; then
      if [[ "$port" != "$requested_port" ]]; then
        echo "${label} port ${requested_port} is in use; using ${port}." >&2
      fi
      echo "$port"
      return
    fi
    port=$((port + 1))
  done

  echo "No free ${label} port found in ${requested_port}-${max_port}." >&2
  exit 1
}

validate_port "$REQUESTED_API_PORT" "API"
validate_port "$REQUESTED_WEB_PORT" "web"
API_PORT="$(choose_port "$API_HOST" "$REQUESTED_API_PORT" "API" "HELLOBEAUTY_API_PORT")"
WEB_PORT="$(choose_port "$WEB_HOST" "$REQUESTED_WEB_PORT" "web" "HELLOBEAUTY_WEB_PORT")"
API_ORIGIN="http://${API_HOST}:${API_PORT}"
WEB_URL="${HELLOBEAUTY_WEB_URL:-http://${WEB_HOST}:${WEB_PORT}/}"

export HELLOBEAUTY_WEB_URL="$WEB_URL"
export HELLOBEAUTY_API_PROXY_TARGET="${HELLOBEAUTY_API_PROXY_TARGET:-$API_ORIGIN}"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-$API_ORIGIN}"
export HELLOBEAUTY_CORS_ORIGINS="${HELLOBEAUTY_CORS_ORIGINS:-http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT},http://localhost:10086,http://127.0.0.1:10086}"

pids=()

cleanup() {
  local code=$?
  for pid in "${pids[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  if ((${#pids[@]} > 0)); then
    wait "${pids[@]}" >/dev/null 2>&1 || true
  fi
  exit "$code"
}
trap cleanup INT TERM EXIT

echo "HelloBeauty local services"
echo "API:      ${API_ORIGIN}"
echo "Docs:     ${API_ORIGIN}/docs"
echo "Health:   ${API_ORIGIN}/api/health"
echo "Web:      ${WEB_URL}"
echo

"$PYTHON_BIN" -m uvicorn backend.app:app --host "$API_HOST" --port "$API_PORT" --reload &
pids+=("$!")

if [[ "$START_WEB" == "1" || "$START_WEB" == "true" || "$START_WEB" == "yes" ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm --workspace apps/web run dev -- --hostname "$WEB_HOST" --port "$WEB_PORT" &
    pids+=("$!")
  else
    echo "npm was not found; backend is running, but the web dev server was not started." >&2
  fi
else
  echo "Web dev server skipped because HELLOBEAUTY_START_WEB=${START_WEB}."
fi

while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      wait "$pid"
      exit $?
    fi
  done
  sleep 2
done
