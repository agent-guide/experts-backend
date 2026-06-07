#!/usr/bin/env bash
# Run the backend locally for testing.
# Bypasses any SOCKS/HTTP proxy for loopback so calls to the local ngent
# (127.0.0.1) and the SQLite file work, while keeping the proxy for external hosts.
set -euo pipefail

cd "$(dirname "$0")/.."

export no_proxy="127.0.0.1,localhost,::1${no_proxy:+,$no_proxy}"
export NO_PROXY="$no_proxy"

PY="${PYTHON:-.venv/bin/python}"

exec "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 15000 "$@"
