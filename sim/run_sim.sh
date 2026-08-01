#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
echo "Enrollment QR payload (simulated): DGXSPARK:SIM-0001:simulated-pubkey"
(cd agent && uv run python -m sparkd_provision --mock --port 8080) &
agent_pid=$!
trap 'kill "$agent_pid"' EXIT INT TERM
cd app
VITE_AGENT_URL=http://127.0.0.1:8080 npm run dev -- --host 127.0.0.1
