# pravburo-reff-site

Публичный сервис агентской программы Правбюро.

Отвечает за регистрацию и вход агентов, кабинет, реферальную форму, QR-код,
защиту от спама и read-only интеграцию с клиентским ЛК. Прямого Bitrix-клиента и
логики изменения выплат в этом репозитории нет.

## Common submodule

Модели и схема БД подключены из `pravburo-reff-common`:

```bash
git clone --recurse-submodules https://github.com/zadkie1ll/pravburo-reff-site.git
git submodule update --init --recursive
```

При обновлении общей схемы:

```bash
git submodule update --remote common
```

## Запуск

Сначала нужно собрать фронтенд (страницы сайта раздаются из `frontend/dist`, см. ниже):

```bash
(cd frontend && npm ci && npm run build)
cp .env.example .env
uv sync
uv run uvicorn src.site.main:app --host 0.0.0.0 --port 8000
```

Через Docker:

```bash
docker compose up --build -d
```

На production Compose использует host network, как существующие backend-сервисы
Правбюро, и слушает только `127.0.0.1:8040`.

## Внешние зависимости

- `pravburo-reff-crm`: создание лида и получение телефона контакта;
- выделенная PostgreSQL `pravburo_ref`: агентские данные;
- production Django PostgreSQL `bd`: только read-only legacy mapping;
- SMTP, Turnstile и OAuth-провайдеры.

Внутренние запросы к CRM подписываются заголовком `X-Internal-Token`.

## Проверки

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Фронтенд (React)

Все страницы сайта (публичные, кабинет партнёра, админка) это одно React-приложение в `frontend/`:
Vite, React, TypeScript (strict), React Router, TanStack Query, Vitest. Node 22 (`frontend/.nvmrc`).
Бэкенд отдаёт только JSON API (`/api/v1/site/...`), несколько файлов (QR, PDF выплат), серверные
шаги входа через Telegram/Яндекс и внутренние API для соседних сервисов.

Структура `frontend/src`: `app/` (роутер, layout, защита маршрутов), `features/<раздел>/`
(страницы, запросы, типы), `shared/` (API-клиент, общие компоненты), `styles/` (CSS по частям).

Разработка с горячей перезагрузкой (бэкенд запущен отдельно на :8040, иначе задайте
`VITE_BACKEND_URL`):

```bash
cd frontend
npm install
npm run dev
```

Проверки и сборка:

```bash
npm test               # Vitest
npm run lint           # ESLint (в т.ч. запрет inline style: этого требует CSP)
npm run typecheck
npm run build          # сборка в frontend/dist; её раздаёт FastAPI
```

Без `frontend/dist` бэкенд не отдаёт страницы (работает только API) и пишет предупреждение в лог.
Docker-образ собирает фронтенд отдельной стадией, в образ попадает готовый `dist`. За nginx нужен
`location /assets/` на бэкенд (см. `deploy/nginx/`).

**Как добавить страницу.** Маршрут в `frontend/src/app/App.tsx`, путь в
`frontend/src/app/spaRoutes.ts` и в `src/web/routes/spa.py`. Тест
`tests/test_api_site.py::test_spa_paths_match_the_frontend_route_list` следит, чтобы списки
совпадали.

**API.** Ошибки всегда `{"error": {"code", "message", "fields"}}` (`src/web/api_errors.py`),
доступ через `ApiAgent` / `ApiPartner` / `ApiAdmin` (`src/web/api_dependencies.py`), изменяющие
запросы защищены заголовком `X-CSRF-Token` (токен отдаёт `GET /api/v1/site/me`).

## Демо для ручной проверки

Изолированное окружение с готовыми демо-данными (своя временная БД в Docker, заглушка CRM, сайт на
:8050). Не трогает рабочие базы и сервисы, письма с кодами пишутся в лог.

```bash
scripts/react_demo/start.sh
scripts/react_demo/stop.sh
```

Аккаунты и сценарии проверки: `docs/manual-test-checklist.md`. История переноса с Jinja на React:
`docs/react-migration-plan.md`.
