#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

HOST="${AVATAR_DASHBOARD_HOST:-127.0.0.1}"
PORT="${AVATAR_DASHBOARD_PORT:-8787}"
SYSTEM_ADDRESS="${AVATAR_SYSTEM_ADDRESS:-udp://:14540}"
CAMERA_URL="${AVATAR_CAMERA_URL:-${AVATAR_SIM_CAMERA_URL:-}}"

args=(--host "$HOST" --port "$PORT" --system-address "$SYSTEM_ADDRESS")
if [[ -n "$CAMERA_URL" ]]; then
  args+=(--camera-url "$CAMERA_URL")
fi
if [[ -n "${AVATAR_AGENT_WEBHOOK_URL:-}" ]]; then
  args+=(--agent-webhook-url "$AVATAR_AGENT_WEBHOOK_URL")
fi
if [[ "${AVATAR_DASHBOARD_DEMO:-0}" == "1" ]]; then
  args+=(--demo)
fi

exec "$PYTHON_BIN" -m avatar.dashboard.server "${args[@]}"
