#!/usr/bin/env bash
# Останавливает демо и удаляет его временную базу.
SITE="$(cd "$(dirname "$0")/../.." && pwd)"
DEMO="$SITE/.demo"
for name in server crm; do
  if [ -f "$DEMO/$name.pid" ]; then
    kill "$(cat "$DEMO/$name.pid")" 2>/dev/null || true
    rm -f "${DEMO:?}/${name:?}.pid"
  fi
done
docker rm -f reff-demo-pg >/dev/null 2>&1 || true
echo "Демо остановлено."
