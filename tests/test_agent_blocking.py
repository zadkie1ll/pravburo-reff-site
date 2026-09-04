import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentCredential, EmploymentFormat
from sqlalchemy import delete

from src.core.security import hash_password
from src.main import app


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


async def _make_agent(*, is_active: bool, blocked_reason: str | None = None) -> tuple[int, str]:
    email = f"{uuid.uuid4()}@example.test"
    async with session_factory() as session:
        agent = Agent(
            email=email,
            display_name="Тест",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
            is_active=is_active,
            blocked_reason=blocked_reason,
        )
        session.add(agent)
        await session.flush()
        session.add(AgentCredential(agent_id=agent.id, password_hash=hash_password("demo12345")))
        await session.commit()
        return agent.id, email


async def _delete_agent(agent_id: int) -> None:
    async with session_factory() as session:
        await session.execute(delete(AgentCredential).where(AgentCredential.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_blocked_agent_cannot_log_in() -> None:
    agent_id, email = await _make_agent(
        is_active=False, blocked_reason="Подозрение на мошенничество"
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            login_page = await client.get("/login")
            csrf = login_page.text.split('name="csrf" value="')[1].split('"')[0]
            response = await client.post(
                "/login",
                data={"email": email, "password": "demo12345", "csrf": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 403
            assert "Аккаунт заблокирован" in response.text
            assert "Подозрение на мошенничество" in response.text
    finally:
        await _delete_agent(agent_id)


async def test_active_session_is_kicked_out_once_blocked_mid_session() -> None:
    agent_id, email = await _make_agent(is_active=True)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            login_page = await client.get("/login")
            csrf = login_page.text.split('name="csrf" value="')[1].split('"')[0]
            login_response = await client.post(
                "/login",
                data={"email": email, "password": "demo12345", "csrf": csrf},
                follow_redirects=False,
            )
            assert login_response.status_code == 303

            # a page that requires CurrentAgent still works while active
            still_ok = await client.get("/profile")
            assert still_ok.status_code == 200

            # admin blocks the account mid-session
            async with session_factory() as session:
                agent = await session.get(Agent, agent_id)
                agent.is_active = False
                agent.blocked_reason = "Заблокирован админом"
                await session.commit()

            kicked_out = await client.get("/profile", follow_redirects=False)
            assert kicked_out.status_code == 303
            assert kicked_out.headers["location"] == "/login"
    finally:
        await _delete_agent(agent_id)
