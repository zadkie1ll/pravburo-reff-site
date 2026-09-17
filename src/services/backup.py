import asyncio
import gzip
import logging
import os
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pravburo_ref_common.config import get_common_settings

from src.core.telegram import send_backup_document, send_backup_failed_notice

logger = logging.getLogger(__name__)


async def _dump_database() -> bytes:
    """Run pg_dump against the same database the app itself connects to
    (parsed out of DATABASE_URL) and gzip the plain-SQL output.

    Requires the postgresql-client package matching the server's major
    version to be installed in the image - pg_dump refuses to run against
    a newer server than itself.
    """
    url = urlsplit(get_common_settings().database_url.replace("+asyncpg", ""))
    args = [
        "pg_dump",
        "--host",
        url.hostname or "localhost",
        "--port",
        str(url.port or 5432),
        "--username",
        url.username or "",
        "--no-password",
        "--format=plain",
        (url.path or "").lstrip("/"),
    ]
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PGPASSWORD": url.password or ""},
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"pg_dump exited with code {process.returncode}: "
            f"{stderr.decode(errors='replace')[:500]}"
        )
    return gzip.compress(stdout)


async def _notify_failure(message: str) -> None:
    try:
        await send_backup_failed_notice(message)
    except Exception:
        logger.exception("Failed to send backup-failure admin notice as well")


async def run_daily_backup() -> None:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"pravburo_ref_{today}.sql.gz"

    try:
        content = await _dump_database()
    except Exception:
        logger.exception("Database backup dump failed")
        await _notify_failure(f"pg_dump не выполнился, бэкап за {today} не создан")
        return

    try:
        await send_backup_document(content, filename, caption=f"Бэкап БД за {today}")
    except Exception:
        logger.exception("Sending backup document to Telegram failed")
        await _notify_failure(f"pg_dump прошёл, но отправка в Telegram не удалась ({today})")
