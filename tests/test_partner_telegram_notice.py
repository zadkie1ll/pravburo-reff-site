import uuid

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentIdentity
from sqlalchemy import delete

from src.core.config import get_settings
from src.core.telegram import send_partner_notice


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_send_partner_notice_is_a_noop_without_bot_token(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "")

    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    try:
        # Must not raise even though there's no bot token configured.
        await send_partner_notice(session, agent_id, "Привет")
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_send_partner_notice_is_a_noop_without_linked_telegram(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")

    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    try:
        # No AgentIdentity(provider="telegram") row for this agent - must not raise.
        await send_partner_notice(session, agent_id, "Привет")
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_send_partner_notice_sends_to_linked_telegram_chat_id(monkeypatch) -> None:
    import src.core.telegram as telegram_module

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")

    sent: list[tuple[str, str, str]] = []

    async def fake_send_message(token, chat_id, message):
        sent.append((token, chat_id, message))

    monkeypatch.setattr(telegram_module, "_send_message", fake_send_message)

    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.flush()
        session.add(
            AgentIdentity(agent_id=agent.id, provider="telegram", subject="123456789")
        )
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            await send_partner_notice(session, agent_id, "Ваша выплата произведена.")
        assert sent == [("test-token", "123456789", "Ваша выплата произведена.")]
    finally:
        async with session_factory() as session:
            await session.execute(delete(AgentIdentity).where(AgentIdentity.agent_id == agent_id))
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()
