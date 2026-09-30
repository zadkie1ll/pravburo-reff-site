#!/usr/bin/env bash
# Поднимает демо для ручной проверки React-фронтенда:
#   сайт http://127.0.0.1:8050, БД в Docker на 5433, заглушка CRM на 8042.
# Не трогает вашу dev-БД (5540) и сервер на 8040. Остановить: scripts/react_demo/stop.sh
set -euo pipefail

SITE="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO="$SITE/.demo"
mkdir -p "$DEMO"

"$SITE/scripts/react_demo/stop.sh" >/dev/null 2>&1 || true

echo "→ База данных (Docker, порт 5433)"
docker run --rm -d --name reff-demo-pg -p 127.0.0.1:5433:5432 \
  -e POSTGRES_USER=demo -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=demo postgres:16-alpine >/dev/null
until docker exec reff-demo-pg pg_isready -U demo -d demo >/dev/null 2>&1; do sleep 1; done
sleep 2

export DATABASE_URL="postgresql+asyncpg://demo:demo@127.0.0.1:5433/demo"
export LEGACY_DATABASE_URL="postgresql+asyncpg://demo:demo@127.0.0.1:5433/legacy"

echo "→ Миграции и демо-данные"
(cd "$SITE/../pravburo-reff-common" && uv run alembic upgrade head >/dev/null 2>&1)
PYTHONPATH="$SITE" "$SITE/.venv/bin/python" "$SITE/scripts/react_demo/demo_data.py" seed

if [ ! -f "$SITE/frontend/dist/index.html" ] || [ "${1:-}" = "--build" ]; then
  echo "→ Сборка фронтенда"
  (cd "$SITE/frontend" && npm install --silent && npm run build --silent)
fi

echo "→ Заглушка CRM (порт 8042)"
nohup python3 "$SITE/scripts/react_demo/fake_crm.py" >"$DEMO/crm.log" 2>&1 &
echo $! >"$DEMO/crm.pid"

echo "→ Сайт (порт 8050)"
# Запуск из папки без .env: настоящие ключи Telegram/SMTP не подхватываются.
cd "$DEMO"
APP_ENV=development PUBLIC_BASE_URL="http://127.0.0.1:8050" \
TURNSTILE_SITE_KEY=1x00000000000000000000AA TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA \
PYTHONPATH="$SITE" nohup "$SITE/.venv/bin/python" -m uvicorn src.site.main:app --port 8050 \
  >"$DEMO/server.log" 2>&1 &
echo $! >"$DEMO/server.pid"

for _ in $(seq 1 30); do
  curl -fs http://127.0.0.1:8050/health/live >/dev/null 2>&1 && break
  sleep 1
done

cat <<MSG

Готово: http://127.0.0.1:8050
Пароль у всех демо-аккаунтов: demo12345 (аккаунты и что проверять: docs/manual-test-checklist.md)
Письма с кодами (регистрация, сброс пароля, смена почты) пишутся в лог:
  grep "Development email" "$DEMO/server.log" | tail -3
MSG
