#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${RUFLEX_PYTHON:-$ROOT/.venv/bin/python}"
API_PORT="${RUFLEX_API_PORT:-8010}"
STUDIO_PORT="${RUFLEX_STUDIO_PORT:-5173}"
API_PID=""
STUDIO_PID=""

fail() { printf 'RuFLEX Studio: %s\n' "$*" >&2; exit 1; }

[[ -x "$PYTHON_BIN" ]] || fail "Python environment not found at '$PYTHON_BIN'. Create .venv and install '.[dev,studio]' first, or set RUFLEX_PYTHON."
command -v node >/dev/null 2>&1 || fail "Node.js is required; install the Node.js version declared by the project before starting RuFLEX."
[[ -f "$ROOT/frontend/node_modules/vite/bin/vite.js" ]] || fail "Frontend dependencies are missing. Run 'cd frontend && npm ci' first; this launcher never installs packages."

"$PYTHON_BIN" - <<'PY' || fail "Python 3.11+ with RuFLEX and uvicorn is required in the selected environment."
import sys
if sys.version_info < (3, 11):
    raise SystemExit(1)
import ruflex.api.main  # noqa: F401
import uvicorn  # noqa: F401
PY

node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (!(major > 22 || (major === 22 && minor >= 12) || (major === 20 && minor >= 19))) process.exit(1)' \
  || fail "Node.js 20.19+ or 22.12+ is required by the current Studio toolchain."

for port in "$API_PORT" "$STUDIO_PORT"; do
  [[ "$port" =~ ^[0-9]+$ ]] || fail "Invalid local port: '$port'."
  port_number=$((10#$port))
  (( port_number > 0 && port_number < 65536 )) || fail "Invalid local port: '$port'."
done
[[ "$API_PORT" != "$STUDIO_PORT" ]] || fail "API and Studio ports must be different."

check_port_available() {
  "$PYTHON_BIN" - "$1" <<'PY'
import socket
import sys
with socket.socket() as sock:
    try:
        sock.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
}

check_port_available "$API_PORT" || fail "127.0.0.1:$API_PORT is already in use; no existing process was changed."
check_port_available "$STUDIO_PORT" || fail "127.0.0.1:$STUDIO_PORT is already in use; no existing process was changed."

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  for pid in "$STUDIO_PID" "$API_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$STUDIO_PID" "$API_PID"; do
    if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
  done
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$ROOT"
RUFLEX_STUDIO_PORT="$STUDIO_PORT" PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -m uvicorn ruflex.api.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

cd "$ROOT/frontend"
VITE_RUFLEX_API_URL="http://127.0.0.1:$API_PORT" node "$ROOT/frontend/node_modules/vite/bin/vite.js" --host 127.0.0.1 --port "$STUDIO_PORT" --strictPort &
STUDIO_PID=$!

wait_for_url() {
  local url="$1" pid="$2" attempt
  for attempt in {1..40}; do
    if ! kill -0 "$pid" 2>/dev/null; then return 1; fi
    if "$PYTHON_BIN" -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=0.5).close()' "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

wait_for_url "http://127.0.0.1:$API_PORT/api/health" "$API_PID" || fail "API failed to become healthy; stopping the Studio process started by this launcher."
wait_for_url "http://127.0.0.1:$STUDIO_PORT/" "$STUDIO_PID" || fail "Studio failed to become ready; stopping the API process started by this launcher."

printf '\nRuFLEX Studio is ready at http://127.0.0.1:%s/\n' "$STUDIO_PORT"
printf 'API health: http://127.0.0.1:%s/api/health\nPress Ctrl-C to stop both RuFLEX child processes.\n\n' "$API_PORT"

set +e
wait -n "$API_PID" "$STUDIO_PID"
status=$?
set -e
printf 'A RuFLEX service exited (status %s); stopping the other launcher-owned service.\n' "$status" >&2
exit 1
