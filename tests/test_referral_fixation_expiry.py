import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication, Reward
from sqlalchemy import delete

from src.core.security import normalize_phone
from src.services.referrals import ApplicationInput, create_first_application


class _FakeLeadDelivery:
    async def create_lead(self, application: ReferralApplication, agent_name: str) -> str:
        return "lead-1"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _make_agent(session, marker: str) -> Agent:
    agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Агент{marker}")
    session.add(agent)
    await session.flush()
    return agent


async def test_second_submission_within_180_days_returns_first_agents_application() -> None:
    marker = uuid.uuid4().hex[:8]
    phone_raw = f"+7999{uuid.uuid4().int % 10**7:07d}"
    phone = normalize_phone(phone_raw)

    async with session_factory() as session:
        first_agent = await _make_agent(session, marker)
        second_agent = await _make_agent(session, marker + "b")
        await session.commit()
        first_agent_id, second_agent_id = first_agent.id, second_agent.id

    try:
        async with session_factory() as session:
            first_agent = await session.get(Agent, first_agent_id)
            application, created = await create_first_application(
                session,
                first_agent,
                ApplicationInput(full_name="Клиент", phone=phone_raw),
                _FakeLeadDelivery(),
            )
            assert created is True
            first_application_id = application.id

        async with session_factory() as session:
            second_agent = await session.get(Agent, second_agent_id)
            application, created = await create_first_application(
                session,
                second_agent,
                ApplicationInput(full_name="Клиент", phone=phone_raw),
                _FakeLeadDelivery(),
            )
            assert created is False
            assert application.id == first_application_id
            assert application.agent_id == first_agent_id
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.phone_normalized == phone)
            )
            await session.execute(
                delete(Agent).where(Agent.id.in_([first_agent_id, second_agent_id]))
            )
            await session.commit()


async def test_expired_unpaid_fixation_lets_a_new_agent_claim_the_phone() -> None:
    marker = uuid.uuid4().hex[:8]
    phone_raw = f"+7999{uuid.uuid4().int % 10**7:07d}"
    phone = normalize_phone(phone_raw)

    async with session_factory() as session:
        first_agent = await _make_agent(session, marker)
        second_agent = await _make_agent(session, marker + "b")
        await session.flush()
        stale_application = ReferralApplication(
            agent_id=first_agent.id,
            full_name="Клиент",
            phone_normalized=phone,
            created_at=datetime.now(UTC) - timedelta(days=181),
        )
        session.add(stale_application)
        await session.commit()
        first_agent_id, second_agent_id = first_agent.id, second_agent.id
        stale_application_id = stale_application.id

    try:
        async with session_factory() as session:
            second_agent = await session.get(Agent, second_agent_id)
            application, created = await create_first_application(
                session,
                second_agent,
                ApplicationInput(full_name="Клиент", phone=phone_raw),
                _FakeLeadDelivery(),
            )
            assert created is True
            assert application.id != stale_application_id
            assert application.agent_id == second_agent_id
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.phone_normalized == phone)
            )
            await session.execute(
                delete(Agent).where(Agent.id.in_([first_agent_id, second_agent_id]))
            )
            await session.commit()


async def test_paid_fixation_never_expires() -> None:
    marker = uuid.uuid4().hex[:8]
    phone_raw = f"+7999{uuid.uuid4().int % 10**7:07d}"
    phone = normalize_phone(phone_raw)

    async with session_factory() as session:
        first_agent = await _make_agent(session, marker)
        second_agent = await _make_agent(session, marker + "b")
        await session.flush()
        old_application = ReferralApplication(
            agent_id=first_agent.id,
            full_name="Клиент",
            phone_normalized=phone,
            created_at=datetime.now(UTC) - timedelta(days=400),
        )
        session.add(old_application)
        await session.flush()
        session.add(
            Reward(
                deal_id=str(uuid.uuid4()),
                application_id=old_application.id,
                agent_id=first_agent.id,
                amount=Decimal("1000.00"),
            )
        )
        await session.commit()
        first_agent_id, second_agent_id = first_agent.id, second_agent.id
        old_application_id = old_application.id

    try:
        async with session_factory() as session:
            second_agent = await session.get(Agent, second_agent_id)
            application, created = await create_first_application(
                session,
                second_agent,
                ApplicationInput(full_name="Клиент", phone=phone_raw),
                _FakeLeadDelivery(),
            )
            assert created is False
            assert application.id == old_application_id
            assert application.agent_id == first_agent_id
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(Reward).where(Reward.application_id == old_application_id)
            )
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.phone_normalized == phone)
            )
            await session.execute(
                delete(Agent).where(Agent.id.in_([first_agent_id, second_agent_id]))
            )
            await session.commit()
