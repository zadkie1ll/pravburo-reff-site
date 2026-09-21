import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


class _FakeSession:
    def __init__(self, agent) -> None:
        self._agent = agent

    async def get(self, model, agent_id):
        return self._agent


def _request(path: str):
    return SimpleNamespace(session={"agent_id": 1}, url=SimpleNamespace(path=path))


def _agent(**overrides) -> SimpleNamespace:
    defaults = dict(role=AgentRole.AGENT, employment_format=None, is_active=True)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize("path", ["/cabinet", "/payouts", "/profile", "/cabinet/visits"])
async def test_agent_without_employment_format_is_sent_to_onboarding(path) -> None:
    with pytest.raises(HTTPException) as exc:
        await require_agent(_request(path), _FakeSession(_agent()))

    assert exc.value.status_code == 303
    assert exc.value.headers["Location"] == "/onboarding"


async def test_onboarding_page_itself_is_reachable_without_format() -> None:
    agent = _agent()
    assert await require_agent(_request("/onboarding"), _FakeSession(agent)) is agent


async def test_agent_with_format_and_admins_use_the_cabinet_freely() -> None:
    with_format = _agent(employment_format=EmploymentFormat.SELF_EMPLOYED)
    assert await require_agent(_request("/cabinet"), _FakeSession(with_format)) is with_format

    admin = _agent(role=AgentRole.ADMIN)
    assert await require_agent(_request("/admin"), _FakeSession(admin)) is admin


def _csrf_from(html: str) -> str:
    return html.split('name="csrf" value="')[1].split('"')[0]


async def _make_agent(employment_format=None) -> Agent:
    async with session_factory() as session:
        agent = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name="Партнёр",
            employment_format=employment_format,
        )
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


async def _delete_agent(agent_id: int) -> None:
    async with session_factory() as session:
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_choosing_a_format_saves_it_and_opens_the_cabinet() -> None:
    agent = await _make_agent()
    app.dependency_overrides[require_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            page = await client.get("/onboarding")
            assert page.status_code == 200
            for title in ("Самозанятый", "ИП", "Физическое лицо"):
                assert title in page.text
            assert "Написать менеджеру" in page.text
            assert "налог 4%" in page.text and "43%" in page.text

            response = await client.post(
                "/onboarding",
                data={"employment_format": "self_employed", "csrf": _csrf_from(page.text)},
                follow_redirects=False,
            )
        async with session_factory() as session:
            stored = await session.get(Agent, agent.id)
            saved_format = stored.employment_format
    finally:
        app.dependency_overrides.pop(require_agent, None)
        await _delete_agent(agent.id)

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
    assert saved_format == EmploymentFormat.SELF_EMPLOYED


async def test_choice_without_valid_csrf_is_rejected() -> None:
    agent = await _make_agent()
    app.dependency_overrides[require_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/onboarding")
            response = await client.post(
                "/onboarding",
                data={"employment_format": "individual", "csrf": "wrong"},
                follow_redirects=False,
            )
        async with session_factory() as session:
            stored = await session.get(Agent, agent.id)
            saved_format = stored.employment_format
    finally:
        app.dependency_overrides.pop(require_agent, None)
        await _delete_agent(agent.id)

    assert response.status_code == 400
    assert saved_format is None


async def test_agent_who_already_chose_is_redirected_away_from_onboarding() -> None:
    agent = await _make_agent(EmploymentFormat.INDIVIDUAL)
    app.dependency_overrides[require_agent] = lambda: agent
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/onboarding", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(require_agent, None)
        await _delete_agent(agent.id)

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
