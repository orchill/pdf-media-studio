#!/usr/bin/env bash
# Start PDF & Media Studio (creates venv on first run)
set -e
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "[setup] First run - creating virtual environment..."
  python3 -m venv .venv
  "$PY" -m pip install --upgrade pip -q
  "$PY" -m pip install -r requirements.txt
fi
if [ ! -f "frontend/dist/index.html" ] && command -v npm >/dev/null; then
  echo "[setup] Building web interface..."
  (cd frontend && npm install --no-audit --no-fund >/dev/null 2>&1 && npm run build) || true
fi

exec "$PY" run.py "$@"
