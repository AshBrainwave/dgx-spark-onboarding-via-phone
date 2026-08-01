#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$root_dir/.sim/enrollment-qr.png}"
cd "$root_dir/agent"
SPARK_QR_OUTPUT="$output" uv run python -c 'import os; from pathlib import Path; from sparkd_provision.qr import ascii_qr, enrollment_payload, write_png; p=enrollment_payload("SIM-0001", "DGX-Spark-0001", "SparkSim2345", "simulated-pubkey", "12345678"); write_png(p, Path(os.environ["SPARK_QR_OUTPUT"])); print(ascii_qr(p)); print("Wrote", os.environ["SPARK_QR_OUTPUT"])'
