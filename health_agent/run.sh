#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "Starting Health Agent web server on ${HOST}:${PORT}"
cd "${PROJECT_ROOT}"
python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
