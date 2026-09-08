import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, PushSubscription
from sqlalchemy import delete, select

from src.core.push import send_push_notice
from src.main import app
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_subscribe_requires_login() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/push/subscribe",
            json={"endpoint": "https://example.com/push/1", "keys": {"p256dh": "a", "auth": "b"}},
        )
    assert response.status_code == 303


async def test_subscribe_then_unsubscribe() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    endpoint = f"https://example.com/push/{uuid.uuid4()}"
    app.dependency_overrides[require_agent] = lambda: Agent(id=agent_id, email="x@example.test")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            subscribe_response = await client.post(
                "/push/subscribe",
                json={"endpoint": endpoint, "keys": {"p256dh": "a", "auth": "b"}},
            )
            assert subscribe_response.status_code == 200

            async with session_factory() as session:
                stored = await session.scalar(
                    select(PushSubscription).where(PushSubscription.endpoint == endpoint)
                )
                assert stored is not None
                assert stored.agent_id == agent_id

            unsubscribe_response = await client.post(
                "/push/unsubscribe",
                json={"endpoint": endpoint, "keys": {"p256dh": "a", "auth": "b"}},
            )
            assert unsubscribe_response.status_code == 200

            async with session_factory() as session:
                gone = await session.scalar(
                    select(PushSubscription).where(PushSubscription.endpoint == endpoint)
                )
                assert gone is None
    finally:
        app.dependency_overrides.pop(require_agent, None)
        async with session_factory() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.agent_id == agent_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_send_push_notice_is_a_noop_without_vapid_keys() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.flush()
        session.add(
            PushSubscription(
                agent_id=agent.id,
                endpoint=f"https://example.com/push/{uuid.uuid4()}",
                p256dh="a",
                auth="b",
            )
        )
        await session.commit()
        agent_id = agent.id

    try:
        async with session_factory() as session:
            # No VAPID keys configured in the test environment - must not raise.
            await send_push_notice(session, agent_id, "Тест", "Тестовое тело")
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.agent_id == agent_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()
