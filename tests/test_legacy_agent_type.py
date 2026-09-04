import uuid
from datetime import UTC, datetime

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentCredential
from sqlalchemy import delete

from src.integrations.legacy_lk.gateway import LegacyClientRecord
from src.services.agents import ensure_legacy_client_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    # pytest-asyncio gives each test its own event loop; the shared engine's
    # pooled asyncpg connections are loop-bound, so a stale connection from a
    # previous test's loop breaks here otherwise. Force a fresh pool per test.
    yield
    await engine.dispose()


def _legacy_client(client_id: int) -> LegacyClientRecord:
    return LegacyClientRecord(
        id=client_id,
        name="Тест",
        surname="Тестов",
        middlename=None,
        email=None,
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
        stage_id=1,
    )


async def test_self_registered_agent_keeps_partner_type_after_becoming_a_client() -> None:
    """A partner who consciously registered stays a partner even if they later
    also sign a bankruptcy contract - the legacy-client webhook must not
    downgrade their override tier by attaching legacy_client_id retroactively.
    """
    phone = f"+7999{uuid.uuid4().int % 10**7:07d}"
    async with session_factory() as session:
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            phone_normalized=phone,
            display_name="Партнёр",
        )
        session.add(agent)
        await session.flush()
        session.add(AgentCredential(agent_id=agent.id, password_hash="irrelevant"))
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            found, created = await ensure_legacy_client_agent(
                session, _legacy_client(999001), phone
            )
            assert created is False
            assert found.id == agent_id
            assert found.legacy_client_id is None
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(AgentCredential).where(AgentCredential.agent_id == agent_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_agent_without_own_registration_gets_legacy_client_id_backfilled() -> None:
    """An agent stub with no credentials/identity of their own (e.g. matched by
    phone from an earlier partial import) still gets legacy_client_id filled in -
    only a consciously self-registered account is protected from this.
    """
    phone = f"+7999{uuid.uuid4().int % 10**7:07d}"
    async with session_factory() as session:
        agent = Agent(phone_normalized=phone, display_name="Ещё не привязан")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            found, created = await ensure_legacy_client_agent(
                session, _legacy_client(999002), phone
            )
            assert created is False
            assert found.id == agent_id
            assert found.legacy_client_id == 999002
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_no_match_creates_new_legacy_agent() -> None:
    phone = f"+7999{uuid.uuid4().int % 10**7:07d}"
    async with session_factory() as session:
        found, created = await ensure_legacy_client_agent(session, _legacy_client(999003), phone)
        try:
            assert created is True
            assert found.legacy_client_id == 999003
        finally:
            await session.execute(delete(Agent).where(Agent.id == found.id))
            await session.commit()
