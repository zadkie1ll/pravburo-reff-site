import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    EmploymentFormat,
    ReferralApplication,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import optional_agent

URL = "/api/v1/site/payouts"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _get(agent: Agent | None, params: dict | None = None):
    app.dependency_overrides[optional_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(URL, params=params)
    finally:
        app.dependency_overrides.pop(optional_agent, None)


async def test_guest_and_admin_are_refused() -> None:
    admin = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)

    assert (await _get(None)).status_code == 401
    assert (await _get(admin)).status_code == 403


async def test_unknown_reward_type_is_a_validation_error_not_a_crash() -> None:
    agent = Agent(
        id=1,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )

    response = await _get(agent, {"reward_type": "nonsense"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_rows_and_filter_options_are_returned_and_filters_apply() -> None:
    async with session_factory() as session:
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент Выплатов",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()
        reward = Reward(
            deal_id=str(uuid.uuid4()),
            application_id=application.id,
            agent_id=agent.id,
            reward_type=RewardType.ADVANCE,
            status=RewardStatus.APPROVED,
            amount=Decimal(3000),
            paid_at=datetime.now(UTC),
        )
        session.add(reward)
        await session.commit()
        agent_id, application_id, reward_id = agent.id, application.id, reward.id

    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        everything = await _get(real_agent)
        only_main = await _get(real_agent, {"reward_type": "main"})
        only_paid = await _get(real_agent, {"status": "paid"})
    finally:
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.id == reward_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    body = everything.json()
    assert [row["client_name"] for row in body["rows"]] == ["Клиент Выплатов"]
    assert body["rows"][0]["status_slug"] == "paid"
    assert body["rows"][0]["type_label"] == "Аванс"
    assert {option["value"] for option in body["reward_types"]} >= {"advance", "main"}
    assert {option["value"] for option in body["statuses"]} >= {"paid", "rejected"}
    assert only_main.json()["rows"] == []
    assert [row["status_slug"] for row in only_paid.json()["rows"]] == ["paid"]
