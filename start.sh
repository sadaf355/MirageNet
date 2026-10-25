#!/usr/bin/env bash
set -e

# MirageNet local start script
echo "Starting MirageNet..."

# Start backend in background
(
  cd backend
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  fi
  python3 -m pip install -r requirements.txt -q
  python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

# Start frontend
(
  cd frontend
  npm install
  npm run dev
) &
FRONTEND_PID=$!

cleanup() {
  echo "Shutting down MirageNet..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
