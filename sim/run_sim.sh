#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
./scripts/flash-qr.sh
echo "Enrollment QR payload uses pairing code: 12345678"
(cd agent && uv run python -m sparkd_provision --mock --port 8080) &
agent_pid=$!
trap 'kill "$agent_pid"' EXIT INT TERM
cd app
VITE_AGENT_URL=http://127.0.0.1:8080 npm run dev -- --host 127.0.0.1
