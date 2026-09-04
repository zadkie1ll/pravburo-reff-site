import uuid

import pytest
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication
from sqlalchemy import delete

from src.services.agents import link_agent_to_referrer


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _phone() -> str:
    return f"+7999{uuid.uuid4().int % 10**7:07d}"


async def test_links_new_partner_to_the_agent_who_brought_them_as_a_client() -> None:
    phone = _phone()
    async with session_factory() as session:
        upline = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Оля")
        session.add(upline)
        await session.flush()
        application = ReferralApplication(
            agent_id=upline.id, full_name="Вася", phone_normalized=phone
        )
        session.add(application)
        await session.commit()
        upline_id, application_id = upline.id, application.id

    try:
        async with session_factory() as session:
            new_partner = Agent(
                email=f"{uuid.uuid4()}@example.test", display_name="Вася", phone_normalized=phone
            )
            session.add(new_partner)
            await session.flush()
            await link_agent_to_referrer(session, new_partner)
            await session.commit()
            assert new_partner.invited_by_agent_id == upline_id
            new_partner_id = new_partner.id
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == new_partner_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == upline_id))
            await session.commit()


async def test_no_upline_left_unlinked() -> None:
    phone = _phone()
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", phone_normalized=phone)
        session.add(agent)
        await session.flush()
        await link_agent_to_referrer(session, agent)
        await session.commit()
        assert agent.invited_by_agent_id is None
        agent_id = agent.id

    async with session_factory() as session:
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_does_not_overwrite_an_already_set_upline() -> None:
    phone = _phone()
    async with session_factory() as session:
        first_upline = Agent(email=f"{uuid.uuid4()}@example.test")
        second_upline = Agent(email=f"{uuid.uuid4()}@example.test")
        session.add_all([first_upline, second_upline])
        await session.flush()
        application = ReferralApplication(
            agent_id=second_upline.id, full_name="Клиент", phone_normalized=phone
        )
        session.add(application)
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            phone_normalized=phone,
            invited_by_agent_id=first_upline.id,
        )
        session.add(agent)
        await session.commit()
        first_upline_id = first_upline.id
        second_upline_id = second_upline.id
        application_id = application.id
        agent_id = agent.id

    try:
        async with session_factory() as session:
            reloaded = await session.get(Agent, agent_id)
            await link_agent_to_referrer(session, reloaded)
            await session.commit()
            assert reloaded.invited_by_agent_id == first_upline_id
    finally:
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(
                delete(Agent).where(Agent.id.in_([first_upline_id, second_upline_id]))
            )
            await session.commit()
