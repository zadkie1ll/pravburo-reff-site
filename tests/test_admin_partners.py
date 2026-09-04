import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, ReferralApplication, Reward
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_admin

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


def _csrf_from(html: str) -> str:
    return html.split('name="csrf" value="')[1].split('"')[0]


async def test_partners_page_shows_client_count_and_total_paid() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Партнёр{marker}")
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name="Клиент",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()
        reward = Reward(
            deal_id=str(uuid.uuid4()),
            application_id=application.id,
            agent_id=agent.id,
            amount=Decimal("3000.00"),
        )
        session.add(reward)
        await session.commit()
        agent_id, application_id, reward_id = agent.id, application.id, reward.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/admin/partners?q=Партнёр{marker}")
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.id == reward_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()

    assert response.status_code == 200
    assert f"Партнёр{marker}" in response.text
    assert ">1<" in response.text  # client_count


async def test_block_and_unblock_partner() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Для блокировки")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/partners")
            csrf = _csrf_from(page.text)

            block_response = await client.post(
                f"/admin/partners/{agent_id}/block",
                data={"reason": "Тестовая причина", "csrf": csrf},
                follow_redirects=False,
            )
            assert block_response.status_code == 303

            async with session_factory() as session:
                blocked = await session.get(Agent, agent_id)
                assert blocked.is_active is False
                assert blocked.blocked_reason == "Тестовая причина"

            page2 = await client.get("/admin/partners")
            csrf2 = _csrf_from(page2.text)
            unblock_response = await client.post(
                f"/admin/partners/{agent_id}/unblock",
                data={"csrf": csrf2},
                follow_redirects=False,
            )
            assert unblock_response.status_code == 303

            async with session_factory() as session:
                unblocked = await session.get(Agent, agent_id)
                assert unblocked.is_active is True
                assert unblocked.blocked_reason is None
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_admin_cannot_be_blocked_via_partners_panel() -> None:
    async with session_factory() as session:
        target_admin = Agent(
            email=f"{uuid.uuid4()}@example.test", role=AgentRole.ADMIN, display_name="Другой админ"
        )
        session.add(target_admin)
        await session.commit()
        target_admin_id = target_admin.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/partners")
            csrf = _csrf_from(page.text)
            await client.post(
                f"/admin/partners/{target_admin_id}/block",
                data={"reason": "Ошибка", "csrf": csrf},
                follow_redirects=False,
            )

        async with session_factory() as session:
            still_active = await session.get(Agent, target_admin_id)
            assert still_active.is_active is True
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == target_admin_id))
            await session.commit()


async def test_save_note() -> None:
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name="Для заметки")
        session.add(agent)
        await session.commit()
        agent_id = agent.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/partners")
            csrf = _csrf_from(page.text)
            response = await client.post(
                f"/admin/partners/{agent_id}/note",
                data={"note": "Проверенный партнёр", "csrf": csrf},
                follow_redirects=False,
            )
            assert response.status_code == 303

        async with session_factory() as session:
            updated = await session.get(Agent, agent_id)
            assert updated.admin_note == "Проверенный партнёр"
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()
