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

```bash
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

## UI preview

Каталог страниц с фиктивными данными:

```text
/preview?token=preview-demo-token
```

Заглушка реферальной формы:

```text
/preview/referral/00000000-0000-4000-8000-000000000001?token=preview-demo-token
```

Перед публикацией замените `UI_PREVIEW_TOKEN`.

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
