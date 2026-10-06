#!/usr/bin/env bash
set -euo pipefail
BENCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCH_PYTHON="${BENCH_PYTHON:-$BENCH_ROOT/.venv/bin/python}"
if [[ ! -x "$BENCH_PYTHON" ]]; then BENCH_PYTHON=python3; fi
exec "$BENCH_PYTHON" "$BENCH_ROOT/environments/k3s/lifecycle.py" setup "${1:-simple-01}"
