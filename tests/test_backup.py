import src.core.telegram as telegram_module
import src.services.backup as backup_module
from src.core.config import get_settings
from src.core.telegram import send_backup_document
from src.services.backup import run_daily_backup


async def test_send_backup_document_is_a_noop_without_dump_chat_id(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notification_bot_token", "test-token")
    monkeypatch.setattr(settings, "dump_chat_id", "")

    called = False

    async def fake_send_document(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(telegram_module, "_send_document", fake_send_document)

    # Must not raise even though there's no destination chat configured.
    await send_backup_document(b"dump bytes", "backup.sql.gz")
    assert called is False


async def test_send_backup_document_passes_thread_id_through(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_notification_bot_token", "test-token")
    monkeypatch.setattr(settings, "dump_chat_id", "-100123")
    monkeypatch.setattr(settings, "dump_message_thread_id", "8")

    calls: list[tuple] = []

    async def fake_send_document(
        token, chat_id, content, filename, caption="", message_thread_id=""
    ):
        calls.append((token, chat_id, content, filename, caption, message_thread_id))

    monkeypatch.setattr(telegram_module, "_send_document", fake_send_document)

    await send_backup_document(b"dump bytes", "backup.sql.gz", caption="Бэкап за 2026-09-17")

    assert calls == [
        ("test-token", "-100123", b"dump bytes", "backup.sql.gz", "Бэкап за 2026-09-17", "8")
    ]


async def test_run_daily_backup_sends_document_on_success(monkeypatch) -> None:
    sent_documents: list[tuple[bytes, str]] = []
    failure_notices: list[str] = []

    async def fake_dump_database():
        return b"gzip bytes"

    async def fake_send_backup_document(content, filename, caption=""):
        sent_documents.append((content, filename))

    async def fake_send_backup_failed_notice(reason):
        failure_notices.append(reason)

    monkeypatch.setattr(backup_module, "_dump_database", fake_dump_database)
    monkeypatch.setattr(backup_module, "send_backup_document", fake_send_backup_document)
    monkeypatch.setattr(backup_module, "send_backup_failed_notice", fake_send_backup_failed_notice)

    await run_daily_backup()

    assert len(sent_documents) == 1
    assert sent_documents[0][0] == b"gzip bytes"
    assert failure_notices == []


async def test_run_daily_backup_notifies_when_dump_fails(monkeypatch) -> None:
    failure_notices: list[str] = []
    sent_documents: list[tuple] = []

    async def fake_dump_database():
        raise RuntimeError("pg_dump exited with code 1: connection refused")

    async def fake_send_backup_document(content, filename, caption=""):
        sent_documents.append((content, filename))

    async def fake_send_backup_failed_notice(reason):
        failure_notices.append(reason)

    monkeypatch.setattr(backup_module, "_dump_database", fake_dump_database)
    monkeypatch.setattr(backup_module, "send_backup_document", fake_send_backup_document)
    monkeypatch.setattr(backup_module, "send_backup_failed_notice", fake_send_backup_failed_notice)

    await run_daily_backup()

    assert sent_documents == []
    assert len(failure_notices) == 1
    assert "pg_dump" in failure_notices[0]


async def test_run_daily_backup_notifies_when_telegram_send_fails(monkeypatch) -> None:
    failure_notices: list[str] = []

    async def fake_dump_database():
        return b"gzip bytes"

    async def fake_send_backup_document(content, filename, caption=""):
        raise RuntimeError("Telegram rejected document for chat_id=-100123")

    async def fake_send_backup_failed_notice(reason):
        failure_notices.append(reason)

    monkeypatch.setattr(backup_module, "_dump_database", fake_dump_database)
    monkeypatch.setattr(backup_module, "send_backup_document", fake_send_backup_document)
    monkeypatch.setattr(backup_module, "send_backup_failed_notice", fake_send_backup_failed_notice)

    await run_daily_backup()

    assert len(failure_notices) == 1
    assert "Telegram" in failure_notices[0]


async def test_run_daily_backup_swallows_failure_notice_errors_too(monkeypatch) -> None:
    async def fake_dump_database():
        raise RuntimeError("boom")

    async def fake_send_backup_failed_notice(reason):
        raise RuntimeError("telegram is down too")

    monkeypatch.setattr(backup_module, "_dump_database", fake_dump_database)
    monkeypatch.setattr(backup_module, "send_backup_failed_notice", fake_send_backup_failed_notice)

    # Must not raise even when the failure-notice channel is also broken.
    await run_daily_backup()
