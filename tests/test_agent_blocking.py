import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentCredential, EmploymentFormat
from sqlalchemy import delete

from src.core.security import hash_password
from src.main import app
from src.services.protection import login_rate_limiter


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


async def _api_login(client: AsyncClient, email: str):
    me = (await client.get("/api/v1/site/me")).json()
    return await client.post(
        "/api/v1/site/auth/login",
        json={"email": email, "password": "demo12345"},
        headers={"X-CSRF-Token": me["csrf_token"]},
    )


async def test_blocked_agent_cannot_log_in() -> None:
    login_rate_limiter.reset()
    agent_id, email = await _make_agent(
        is_active=False, blocked_reason="Подозрение на мошенничество"
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await _api_login(client, email)
    finally:
        await _delete_agent(agent_id)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_blocked"
    assert "Подозрение на мошенничество" in response.json()["error"]["message"]


async def test_active_session_is_kicked_out_once_blocked_mid_session() -> None:
    login_rate_limiter.reset()
    agent_id, email = await _make_agent(is_active=True)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await _api_login(client, email)).status_code == 200

            # a page that requires an active partner still works while active
            assert (await client.get("/api/v1/site/profile")).status_code == 200

            # an admin blocks the account mid-session
            async with session_factory() as session:
                agent = await session.get(Agent, agent_id)
                agent.is_active = False
                agent.blocked_reason = "Заблокирован админом"
                await session.commit()

            kicked_out = await client.get("/api/v1/site/profile")
            assert kicked_out.status_code == 401
            # ...and the session itself is ended, not just refused once
            assert (await client.get("/api/v1/site/me")).json()["authenticated"] is False
    finally:
        await _delete_agent(agent_id)
