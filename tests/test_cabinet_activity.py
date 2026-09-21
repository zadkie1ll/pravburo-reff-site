import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    ReferralApplication,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_cabinet_client_table_shows_reward_status_per_client() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Партнёр{marker}")
        session.add(agent)
        await session.flush()

        paid_application = ReferralApplication(
            agent_id=agent.id,
            full_name="Оплативший клиент",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        unpaid_application = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент без оплаты",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add_all([paid_application, unpaid_application])
        await session.flush()

        reward = Reward(
            deal_id=str(uuid.uuid4()),
            application_id=paid_application.id,
            agent_id=agent.id,
        )
        session.add(reward)
        await session.commit()
        agent_id = agent.id
        application_ids = [paid_application.id, unpaid_application.id]
        reward_id = reward.id

    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        app.dependency_overrides[require_agent] = lambda: real_agent
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/cabinet")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.id == reward_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert response.status_code == 200
    assert "Основная выплата: Ожидает решения" in response.text
    assert "Договор не заключен" in response.text


async def test_cabinet_client_table_shows_stage_date_and_totals() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        session.add(agent)
        await session.flush()

        staged = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент на этапе",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
            deal_stage_code="C2:UC_0Y0VBU",
        )
        fresh = ReferralApplication(
            agent_id=agent.id,
            full_name="Свежая заявка",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add_all([staged, fresh])
        await session.flush()

        rewards = [
            Reward(
                deal_id=str(uuid.uuid4()),
                application_id=staged.id,
                agent_id=agent.id,
                reward_type=RewardType.ADVANCE,
                amount=3000,
                status=RewardStatus.APPROVED,
                paid_at=datetime.now(UTC),
            ),
            Reward(
                deal_id=str(uuid.uuid4()),
                application_id=staged.id,
                agent_id=agent.id,
                reward_type=RewardType.MAIN,
                amount=10000,
                status=RewardStatus.APPROVED,
            ),
        ]
        session.add_all(rewards)
        await session.commit()
        agent_id = agent.id
        application_ids = [staged.id, fresh.id]
        created_label = staged.created_at.strftime("%d.%m.%Y")

    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        app.dependency_overrides[require_agent] = lambda: real_agent
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/cabinet")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.agent_id == agent_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert response.status_code == 200
    assert "Заявление подано в суд" in response.text
    assert "Заявка получена" in response.text
    assert "Выплачено: 3 000 ₽ · Ожидается: 10 000 ₽" in response.text
    assert created_label in response.text
