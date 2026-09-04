import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    PayoutSettings,
    ReferralApplication,
    Reward,
    RewardStatus,
)
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_admin

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _csrf_from(html: str) -> str:
    return html.split('name="csrf" value="')[1].split('"')[0]


async def _make_reward(session, *, status, decided_at=None, paid_at=None, marker: str):
    agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Партнёр{marker}")
    session.add(agent)
    await session.flush()
    application = ReferralApplication(
        agent_id=agent.id,
        full_name=f"Клиент{marker}",
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
    )
    session.add(application)
    await session.flush()
    reward = Reward(
        deal_id=str(uuid.uuid4()),
        application_id=application.id,
        agent_id=agent.id,
        amount=Decimal("3000.00"),
        status=status,
        decided_at=decided_at,
        paid_at=paid_at,
    )
    session.add(reward)
    await session.commit()
    return agent.id, application.id, reward.id


async def _cleanup(agent_id, application_id, reward_id):
    async with session_factory() as session:
        await session.execute(delete(Reward).where(Reward.id == reward_id))
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.id == application_id)
        )
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_overdue_reward_shown_as_overdue_on_calendar() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent_id, application_id, reward_id = await _make_reward(
            session,
            status=RewardStatus.APPROVED,
            decided_at=datetime.now(UTC) - timedelta(days=30),
            marker=marker,
        )

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/admin/payouts")
            assert response.status_code == 200
            assert f"Клиент{marker}" in response.text
            assert "Просроченные выплаты" in response.text
    finally:
        app.dependency_overrides.pop(require_admin, None)
        await _cleanup(agent_id, application_id, reward_id)


async def test_mark_paid_sets_paid_at() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent_id, application_id, reward_id = await _make_reward(
            session,
            status=RewardStatus.APPROVED,
            decided_at=datetime.now(UTC) - timedelta(days=2),
            marker=marker,
        )

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/payouts")
            csrf = _csrf_from(page.text)
            response = await client.post(
                f"/admin/payouts/{reward_id}/mark-paid",
                data={"csrf": csrf, "year": "", "month": "", "status": ""},
                follow_redirects=False,
            )
            assert response.status_code == 303

        async with session_factory() as session:
            reward = await session.get(Reward, reward_id)
            assert reward.paid_at is not None
    finally:
        app.dependency_overrides.pop(require_admin, None)
        await _cleanup(agent_id, application_id, reward_id)


async def test_update_overdue_days_setting() -> None:
    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/payouts")
            csrf = _csrf_from(page.text)
            response = await client.post(
                "/admin/payouts/settings",
                data={"overdue_days": "21", "csrf": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 303

        async with session_factory() as session:
            settings = await session.get(PayoutSettings, 1)
            assert settings.overdue_days == 21
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            settings = await session.get(PayoutSettings, 1)
            settings.overdue_days = 14
            await session.commit()
