#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
if ! command -v uv >/dev/null; then
  echo "uv is required: https://docs.astral.sh/uv/" >&2
  exit 1
fi
(cd agent && uv sync --extra dev)
(cd app && npm ci)
./scripts/flash-qr.sh
echo "Enrollment QR payload uses pairing code: 12345678"
(cd agent && uv run python -m sparkd_provision --mock --port 8080) &
agent_pid=$!
trap 'kill "$agent_pid"' EXIT INT TERM
echo "Simulator: http://127.0.0.1:5173 (set SPARK_SIM_FAIL to any documented error code)"
cd app
VITE_AGENT_URL=http://127.0.0.1:8080 npm run dev -- --host 127.0.0.1
