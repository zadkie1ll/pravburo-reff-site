import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, ReferralApplication
from sqlalchemy import delete

from src.main import app
from src.services.referrals import get_application_rows
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _application(agent_id: int, name: str, stage_code: str | None = None) -> ReferralApplication:
    return ReferralApplication(
        agent_id=agent_id,
        full_name=name,
        phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        deal_stage_code=stage_code,
    )


async def _make_agent_with_applications() -> tuple[int, list[int]]:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Партнёр")
        other = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Чужой")
        session.add_all([agent, other])
        await session.flush()
        apps = [
            _application(agent.id, "Клиент без сделки"),
            _application(agent.id, "Клиент думает", "UC_Q6ZN5G"),
            _application(agent.id, "Клиент мусор", "UC_K0Z3P6"),
            _application(agent.id, "Клиент в суде", "C2:UC_0Y0VBU"),
            _application(other.id, "Чужой клиент", "UC_Q6ZN5G"),
        ]
        session.add_all(apps)
        await session.commit()
        return agent.id, [other.id] + [a.id for a in apps]


async def _cleanup(agent_id: int, extra_ids: list[int]) -> None:
    other_id, *application_ids = extra_ids
    async with session_factory() as session:
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.id.in_(application_ids))
        )
        await session.execute(delete(Agent).where(Agent.id.in_([agent_id, other_id])))
        await session.commit()


async def test_application_rows_show_agent_friendly_statuses_for_own_clients_only() -> None:
    agent_id, extra_ids = await _make_agent_with_applications()
    try:
        async with session_factory() as session:
            rows = await get_application_rows(session, agent_id)
    finally:
        await _cleanup(agent_id, extra_ids)

    assert {row.client_name: row.status for row in rows} == {
        "Клиент без сделки": "Заявка получена",
        "Клиент думает": "Думает",
        "Клиент мусор": "Не подходит",
        "Клиент в суде": "Заявление подано в суд",
    }
    assert all("***" in row.masked_phone for row in rows)


async def test_applications_page_and_card_link() -> None:
    agent_id, extra_ids = await _make_agent_with_applications()
    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        app.dependency_overrides[require_agent] = lambda: real_agent
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            page = await client.get("/cabinet/applications")
            cabinet = await client.get("/cabinet")
    finally:
        app.dependency_overrides.pop(require_agent, None)
        await _cleanup(agent_id, extra_ids)

    assert page.status_code == 200
    assert "Клиент думает" in page.text
    assert "Не подходит" in page.text
    assert "Чужой клиент" not in page.text
    assert 'href="/cabinet/applications"' in cabinet.text
