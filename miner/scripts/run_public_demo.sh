#!/usr/bin/env bash
# Start the PoV-R coordinator (stdlib, no secrets) and optionally expose it publicly.
set -euo pipefail
PORT="${PORT:-8787}"; cd "$(dirname "$0")/.."
python3 -m aegis_miner.coordinator "$PORT" & PID=$!; trap 'kill $PID 2>/dev/null' EXIT
sleep 1; curl -s -X POST "http://localhost:$PORT/v1/verify" -H 'Content-Type: application/json' -d '{"text":"2 + 2 = 4"}' >/dev/null && echo "Coordinator OK on :$PORT"
if command -v cloudflared >/dev/null; then
  echo "Starting Cloudflare quick tunnel (URL printed below, ephemeral)…"; cloudflared tunnel --url "http://localhost:$PORT"
else
  cat <<MSG
Expose it publicly with one of:
  cloudflared tunnel --url http://localhost:$PORT      # free, no account
  ngrok http $PORT
Then open: https://bold-thistle-3z5f.here.now/verify.html?coordinator=https://<tunnel-host>
(the page remembers nothing; set localStorage.agisCoordinator to persist)
MSG
  wait $PID
fi
