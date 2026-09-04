import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication, Reward, RewardType
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def test_cabinet_shows_network_summary() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Оля{marker}")
        session.add(agent)
        await session.flush()
        invitee = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Вася{marker}",
            invited_by_agent_id=agent.id,
        )
        session.add(invitee)
        await session.flush()
        application = ReferralApplication(
            agent_id=invitee.id,
            full_name="Клиент",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()

        main_a = Reward(
            deal_id=str(uuid.uuid4()), application_id=application.id, agent_id=invitee.id
        )
        main_b = Reward(
            deal_id=str(uuid.uuid4()), application_id=application.id, agent_id=invitee.id
        )
        session.add_all([main_a, main_b])
        await session.flush()

        override_paid = Reward(
            deal_id=main_a.deal_id,
            application_id=application.id,
            agent_id=agent.id,
            reward_type=RewardType.OVERRIDE,
            amount=Decimal("300.00"),
            network_level=1,
            source_reward_id=main_a.id,
            paid_at=datetime.now(UTC),
        )
        override_pending = Reward(
            deal_id=main_b.deal_id,
            application_id=application.id,
            agent_id=agent.id,
            reward_type=RewardType.OVERRIDE,
            amount=Decimal("150.00"),
            network_level=1,
            source_reward_id=main_b.id,
        )
        session.add_all([override_paid, override_pending])
        await session.commit()
        agent_id, invitee_id, application_id = agent.id, invitee.id, application.id
        reward_ids = [main_a.id, main_b.id, override_paid.id, override_pending.id]

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
            await session.execute(delete(Reward).where(Reward.id.in_(reward_ids)))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == invitee_id))
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert response.status_code == 200
    assert "Моя сеть" in response.text
    assert "300" in response.text
    assert "150" in response.text
