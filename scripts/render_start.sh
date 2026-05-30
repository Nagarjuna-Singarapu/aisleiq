#!/usr/bin/env bash
set -euo pipefail

PUBLIC_PORT="${PORT:-8501}"
INTERNAL_API_PORT="${INTERNAL_API_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

mkdir -p data/db data/videos data/frames data/exports logs

uvicorn app.main:app \
  --host 127.0.0.1 \
  --port "${INTERNAL_API_PORT}" \
  --log-level info &
api_pid=$!

cleanup() {
  kill "${api_pid}" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if "${PYTHON_BIN}" - <<PY
import urllib.request
urllib.request.urlopen("http://127.0.0.1:${INTERNAL_API_PORT}/health", timeout=1)
PY
  then
    break
  fi
  sleep 1
done

export API_BASE_URL="http://127.0.0.1:${INTERNAL_API_PORT}"

exec streamlit run dashboard/app.py \
  --server.address 0.0.0.0 \
  --server.port "${PUBLIC_PORT}" \
  --server.headless true \
  --browser.gatherUsageStats false
