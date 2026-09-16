#!/usr/bin/env bash
# The whole local stack in one terminal: Redis, migrations, the API (reloading),
# a worker, and Vite. Ctrl-C stops all of it. Uses .env for everything else.
set -euo pipefail
cd "$(dirname "$0")/.."

# uvicorn's reloader has been seen to outlive its terminal and keep port 8000.
# If what is on the port is ours, stop it; if it is something else, say so.
for pid in $(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null); do
  if ps -o command= -p "$pid" | grep -q "uvicorn apps.api.app.main"; then
    echo "  stopping the api left over from an earlier run (pid $pid)"
    kill -9 "$pid"
  else
    echo "  port 8000 is in use by pid $pid ($(ps -o comm= -p "$pid")). Stop it first."
    exit 1
  fi
done

docker compose up -d redis >/dev/null
.venv/bin/alembic upgrade head

pids=()
.venv/bin/uvicorn apps.api.app.main:app --reload --port 8000 & pids+=($!)
.venv/bin/python -m apps.worker.main & pids+=($!)
npm --prefix apps/web run dev & pids+=($!)

stop() {
  trap - EXIT INT TERM
  echo
  echo "  stopping. The worker finishes the job it is on first; Ctrl-C again to kill it."
  kill "${pids[@]}" 2>/dev/null || true
  trap 'kill -9 "${pids[@]}" 2>/dev/null || true' INT
  wait "${pids[@]}" 2>/dev/null || true
  pkill -9 -f "uvicorn apps.api.app.main" 2>/dev/null || true
}
trap stop EXIT INT TERM

echo
echo "  api     http://127.0.0.1:8000/docs"
echo "  web     http://localhost:5173"
echo "  worker  running (jobs will not move without it)"
echo
wait
