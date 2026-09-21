import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication, ReferralLinkVisit
from sqlalchemy import delete

from src.main import app
from src.services.referrals import get_visits_by_day
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _make_agent_with_visits() -> int:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        session.add(agent)
        await session.flush()
        session.add_all(
            [
                ReferralLinkVisit(
                    agent_id=agent.id, created_at=datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
                ),
                ReferralLinkVisit(
                    agent_id=agent.id, created_at=datetime(2026, 9, 20, 11, 0, tzinfo=UTC)
                ),
                # 22:30 UTC = 01:30 следующего дня по Москве
                ReferralLinkVisit(
                    agent_id=agent.id, created_at=datetime(2026, 9, 20, 22, 30, tzinfo=UTC)
                ),
                ReferralLinkVisit(
                    agent_id=agent.id, created_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
                ),
            ]
        )
        await session.commit()
        return agent.id


async def _cleanup(agent_id: int, application_ids: tuple[int, ...] = ()) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(ReferralLinkVisit).where(ReferralLinkVisit.agent_id == agent_id)
        )
        if application_ids:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
            )
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_visits_are_grouped_by_moscow_day_newest_first() -> None:
    agent_id = await _make_agent_with_visits()
    try:
        async with session_factory() as session:
            days = await get_visits_by_day(session, agent_id)
    finally:
        await _cleanup(agent_id)

    assert [(day.day_label, day.count) for day in days] == [
        ("21.09.2026", 1),
        ("20.09.2026", 2),
        ("19.09.2026", 1),
    ]


async def test_visits_page_and_cabinet_links() -> None:
    agent_id = await _make_agent_with_visits()
    async with session_factory() as session:
        application = ReferralApplication(
            agent_id=agent_id,
            full_name="Иванов Пётр",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.commit()
        application_id = application.id

    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        app.dependency_overrides[require_agent] = lambda: real_agent
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            visits_page = await client.get("/cabinet/visits")
            cabinet = await client.get("/cabinet")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        await _cleanup(agent_id, (application_id,))

    assert visits_page.status_code == 200
    assert "20.09.2026" in visits_page.text
    assert "Всего" in visits_page.text
    assert 'href="/cabinet/visits"' in cabinet.text
    assert 'href="/payouts"' in cabinet.text  # число договоров ведёт в выплаты
    assert "Иванов Пётр" in cabinet.text  # имя клиента в таблице
