#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -n "${TRAINING_PYTHON:-}" ]]; then
  candidates=("$TRAINING_PYTHON")
else
  candidates=(python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3.14 python3)
fi

selected_python=""
for candidate in "${candidates[@]}"; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    selected_python="$candidate"
    break
  fi
done
if [[ -z "$selected_python" ]]; then
  echo "Python 3.11 or newer is required. Set TRAINING_PYTHON to a compatible interpreter." >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  "$selected_python" -m venv .venv
elif ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
  echo "Existing .venv uses an older Python. Recreate it with Python 3.11 or newer." >&2
  exit 1
fi

if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  .venv/bin/python -m ensurepip --upgrade >/dev/null
fi
.venv/bin/python -m pip install --disable-pip-version-check -r backend/requirements.txt
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build

export TRAINING_DB_PATH="${TRAINING_DB_PATH:-data/training.sqlite3}"
export TRAINING_FRONTEND_DIST="frontend/dist"
.venv/bin/python -c 'import os; from pathlib import Path; from backend.app.seed import seed_demo_data; seed_demo_data(Path(os.environ["TRAINING_DB_PATH"]))'

exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
