#!/usr/bin/env bash
# Ждём, пока контейнер PostgreSQL из docker-compose станет готов принимать подключения.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

POSTGRES_USER="${POSTGRES_USER:-aisdr}"
POSTGRES_DB="${POSTGRES_DB:-aisdr}"

echo "Waiting for PostgreSQL (${POSTGRES_USER}@${POSTGRES_DB})..."
for _ in $(seq 1 90); do
  if docker compose exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
    echo "PostgreSQL is ready."
    exit 0
  fi
  sleep 1
done

echo "Timeout waiting for PostgreSQL." >&2
exit 1
