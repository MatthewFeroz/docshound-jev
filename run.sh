#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "${ROOT}"

PYTHON=""
for candidate in \
  "${ROOT}/.venv/bin/python" \
  "${ROOT}/.venv/Scripts/python.exe" \
  "${ROOT}/backend/.venv/bin/python" \
  "${ROOT}/backend/.venv/Scripts/python.exe"; do
  if [[ -x "${candidate}" ]]; then
    PYTHON="${candidate}"
    break
  fi
done
if [[ -z "${PYTHON}" ]]; then
  echo "Create a Python 3.14 environment and run pip install -r requirements.txt first." >&2
  exit 1
fi
if ! command -v bun >/dev/null 2>&1; then
  echo "Bun 1.3+ is required to build the frontend." >&2
  exit 1
fi

bun install --cwd "${ROOT}/frontend" --frozen-lockfile
bun run --cwd "${ROOT}/frontend" build

exec "${PYTHON}" -m uvicorn app.main:app --app-dir "${ROOT}/backend" \
  --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
