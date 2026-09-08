import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent
from sqlalchemy import delete

from src.core.config import get_settings
from src.main import app
from src.web.routes import internal as internal_route


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_notify_reward_requires_internal_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/rewards/notify",
            json={"agent_id": 1, "reward_type": "advance", "amount": "3000.00"},
        )
    assert response.status_code == 401


async def test_notify_reward_sends_email_push_and_telegram(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    sent_email: list[tuple] = []
    sent_push: list[tuple] = []
    sent_telegram: list[tuple] = []

    async def fake_email(email, type_label, amount_label):
        sent_email.append((email, type_label, amount_label))

    async def fake_push(session, agent_id, title, body):
        sent_push.append((agent_id, title, body))

    async def fake_telegram(session, agent_id, message):
        sent_telegram.append((agent_id, message))

    monkeypatch.setattr(internal_route, "send_reward_notice", fake_email)
    monkeypatch.setattr(internal_route, "send_push_notice", fake_push)
    monkeypatch.setattr(internal_route, "send_partner_notice", fake_telegram)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/rewards/notify",
                headers={"X-Internal-Token": "test-token"},
                json={"agent_id": agent_id, "reward_type": "advance", "amount": "3000.00"},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "notified"}
        assert len(sent_email) == 1
        assert sent_email[0][0] == agent.email
        assert len(sent_push) == 1
        assert len(sent_telegram) == 1
        assert "3 000" in sent_telegram[0][1]
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_notify_reward_ignores_non_notifiable_type(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_service_token", "test-token")

    called: list = []
    monkeypatch.setattr(
        internal_route, "send_reward_notice", lambda *a, **k: called.append("email")
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/rewards/notify",
            headers={"X-Internal-Token": "test-token"},
            json={"agent_id": 1, "reward_type": "override", "amount": "100.00"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert called == []
