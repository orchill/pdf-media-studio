#!/usr/bin/env bash
# Stop PDF & Media Studio (kills the process listening on the given port)
PORT="${1:-8756}"
PIDS="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -z "$PIDS" ]; then
  PIDS="$(pgrep -f "run\.py.*--port ${PORT}" 2>/dev/null || true)"
fi
if [ -z "$PIDS" ]; then
  echo "Nothing listening on port $PORT."
  exit 0
fi
echo "Stopping: $PIDS"
kill $PIDS 2>/dev/null || true
sleep 1
kill -9 $PIDS 2>/dev/null || true
echo "Stopped."
