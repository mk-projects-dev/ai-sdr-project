#!/usr/bin/env bash
# Полный локальный старт: Docker → PostgreSQL → зависимости → API + Next.js
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Частые пути к Node (Homebrew)
export PATH="/opt/homebrew/opt/node@22/bin:/opt/homebrew/opt/node/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

die() {
  echo "error: $*" >&2
  exit 1
}

info() {
  echo "[dev] $*"
}

ensure_root_npm() {
  if [[ ! -d "$ROOT/node_modules" ]]; then
    info "Устанавливаю корневые npm-зависимости (concurrently)…"
    command -v npm >/dev/null 2>&1 || die "npm не найден. Установите Node.js (brew install node)."
    (cd "$ROOT" && npm install)
  fi
}

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  info "Docker недоступен, пробую поднять окружение…"

  if command -v colima >/dev/null 2>&1; then
    info "Запускаю Colima (если уже работает — команда просто завершится)…"
    colima start || true
  elif [[ "$(uname -s)" == "Darwin" ]] && [[ -d "/Applications/Docker.app" ]]; then
    info "Пробую открыть Docker Desktop…"
    open -a Docker 2>/dev/null || true
  fi

  info "Жду доступности Docker…"
  local i
  for i in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      info "Docker готов."
      return 0
    fi
    sleep 2
  done

  die "Docker так и не ответил. Запустите Colima (colima start) или Docker Desktop и повторите."
}

pick_python() {
  local cmd
  for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  die "Не найден python3. Установите Python 3.11+ (brew install python@3.11)."
}

ensure_backend_venv() {
  local py venv="$ROOT/backend/.venv"
  py="$(pick_python)"

  if [[ ! -d "$venv" ]]; then
    info "Создаю venv в backend/.venv ($py)…"
    "$py" -m venv "$venv"
  fi

  if ! "$venv/bin/python" -c "import uvicorn, fastapi, sqlalchemy" >/dev/null 2>&1; then
    info "Ставлю Python-зависимости (pip)…"
    "$venv/bin/pip" install -q --upgrade pip
    "$venv/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
  fi
}

ensure_backend_env_file() {
  local dst="$ROOT/backend/.env"
  if [[ -f "$dst" ]]; then
    return 0
  fi
  if [[ -f "$ROOT/.env.example" ]]; then
    info "Создаю backend/.env из корневого .env.example — проверьте JWT_SECRET и пароли."
    cp "$ROOT/.env.example" "$dst"
    return 0
  fi
  die "Нет backend/.env и нет корневого .env.example."
}

ensure_frontend_deps() {
  command -v npm >/dev/null 2>&1 || die "npm не найден. Установите Node.js."
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    info "Ставлю frontend (npm install)…"
    (cd "$ROOT/frontend" && npm install)
  fi
}

ensure_frontend_env() {
  local ex="$ROOT/frontend/.env.example"
  local dst="$ROOT/frontend/.env.local"
  [[ -f "$ex" ]] || return 0
  if [[ ! -f "$dst" ]]; then
    info "Создаю frontend/.env.local из .env.example"
    cp "$ex" "$dst"
  fi
}

ensure_root_npm
ensure_docker
ensure_backend_env_file
ensure_backend_venv
ensure_frontend_deps
ensure_frontend_env

info "Поднимаю PostgreSQL (docker compose)…"
docker compose up -d db

bash "$ROOT/scripts/wait-for-postgres.sh"

CONCURRENTLY="$ROOT/node_modules/.bin/concurrently"
[[ -x "$CONCURRENTLY" ]] || die "Не найден concurrently; выполните npm install в корне проекта."

info "Запускаю API и фронт (Ctrl+C — остановить всё)…"
exec "$CONCURRENTLY" -k -n api,web -c green,cyan \
  "cd \"$ROOT/backend\" && exec ./.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" \
  "npm run dev --prefix \"$ROOT/frontend\""
