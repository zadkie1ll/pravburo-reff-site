import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    EmploymentFormat,
    ReferralApplication,
    ReferralLinkVisit,
)
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import optional_agent

URL = "/api/v1/site/cabinet"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _get(agent: Agent | None):
    app.dependency_overrides[optional_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(URL)
    finally:
        app.dependency_overrides.pop(optional_agent, None)


async def test_guest_gets_401() -> None:
    response = await _get(None)

    assert response.status_code == 401


async def test_partner_still_onboarding_is_kept_out() -> None:
    fresh = Agent(id=1, email="n@example.test", role=AgentRole.AGENT, is_active=True)

    response = await _get(fresh)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "onboarding_required"


async def test_admin_has_no_cabinet() -> None:
    admin = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)

    response = await _get(admin)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_partner_gets_the_dashboard_data() -> None:
    async with session_factory() as session:
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name="Партнёр Тестов",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент Клиентов",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.commit()
        agent_id, application_id = agent.id, application.id

    try:
        async with session_factory() as session:
            real_agent = await session.get(Agent, agent_id)
        response = await _get(real_agent)
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Партнёр Тестов"
    assert body["referral_url"].endswith(f"/r/{real_agent.referral_code}")
    assert set(body["finance"]) == {
        "total_paid_label",
        "this_month_label",
        "pending_total_label",
        "pending_groups",
    }
    assert body["link_stats"]["applications"] == 1
    assert body["link_stats"]["conversion_rate_label"] == "—"
    level = body["level"]
    assert [node["level"] for node in level["nodes"]] == ["start", "active", "pro", "expert"]
    assert len(level["segment_fills"]) == 3
    assert level["label"] == "Старт"
    assert [client["client_name"] for client in body["clients"]] == ["Клиент Клиентов"]


async def _partner_with_data():
    async with session_factory() as session:
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name="Заявка Заявкина",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        session.add_all([ReferralLinkVisit(agent_id=agent.id) for _ in range(3)])
        await session.commit()
        return agent.id, application.id


async def _cleanup(agent_id: int, application_id: int) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(ReferralLinkVisit).where(ReferralLinkVisit.agent_id == agent_id)
        )
        await session.execute(
            delete(ReferralApplication).where(ReferralApplication.id == application_id)
        )
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def _get_as(path: str, agent: Agent | None):
    app.dependency_overrides[optional_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.pop(optional_agent, None)


@pytest.mark.parametrize("path", [f"{URL}/visits", f"{URL}/applications"])
async def test_list_pages_are_for_partners_only(path) -> None:
    admin = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)

    assert (await _get_as(path, None)).status_code == 401
    assert (await _get_as(path, admin)).status_code == 403


async def test_visits_are_grouped_by_day_with_a_total() -> None:
    agent_id, application_id = await _partner_with_data()
    try:
        async with session_factory() as session:
            agent = await session.get(Agent, agent_id)
        response = await _get_as(f"{URL}/visits", agent)
    finally:
        await _cleanup(agent_id, application_id)

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 3
    assert [day["count"] for day in body["days"]] == [3]
    assert len(body["days"][0]["day_label"]) == 10  # dd.mm.yyyy


async def test_applications_list_the_partners_clients() -> None:
    agent_id, application_id = await _partner_with_data()
    try:
        async with session_factory() as session:
            agent = await session.get(Agent, agent_id)
        response = await _get_as(f"{URL}/applications", agent)
    finally:
        await _cleanup(agent_id, application_id)

    rows = response.json()["rows"]
    assert response.status_code == 200
    assert [row["client_name"] for row in rows] == ["Заявка Заявкина"]
    assert rows[0]["masked_phone"]
    assert rows[0]["status"]
