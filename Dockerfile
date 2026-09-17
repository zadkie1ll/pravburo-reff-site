FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
# postgresql-client-16 (matching the pravburo-reff-postgres server version) for
# the daily pg_dump backup job - pg_dump must not be older than the server.
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $VERSION_CODENAME-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-16 \
    && apt-get purge -y curl gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY common ./common
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "src.site.main:app", "--host", "0.0.0.0", "--port", "8000"]
