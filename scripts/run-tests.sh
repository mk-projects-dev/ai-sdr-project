#!/usr/bin/env bash
# Запуск из корня репозитория (где лежат pytest.ini, tests/, requirements-dev.txt).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found" >&2; exit 1; }
python3 -m pip install -r "${ROOT}/backend/requirements.txt"
python3 -m pip install -r "${ROOT}/requirements-dev.txt"
exec python3 -m pytest "${ROOT}/tests" "$@"
