#!/usr/bin/env bash
# One-time setup: venv + backend deps + (optional) UI build
set -e
cd "$(dirname "$0")/.."

echo "=============================================="
echo " PDF & Media Studio - setup"
echo "=============================================="
command -v python3 >/dev/null || { echo "[error] python3 not found"; exit 1; }

if [ ! -x ".venv/bin/python" ]; then
  echo "[setup] Creating virtual environment..."
  python3 -m venv .venv
fi
echo "[setup] Installing backend dependencies..."
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt

if [ -f "frontend/package.json" ] && command -v npm >/dev/null; then
  echo "[setup] Building web interface..."
  (cd frontend && npm install --no-audit --no-fund && npm run build) || echo "[info] UI build failed - bundled UI will be used if present"
fi

echo "[setup] Done. Start with: scripts/start.sh"
