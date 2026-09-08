import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    DeliveryStatus,
    ProcessingStatus,
    ReferralApplication,
)
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


async def test_applications_page_lists_and_searches() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        agent = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Партнёр{marker}")
        session.add(agent)
        await session.flush()
        application = ReferralApplication(
            agent_id=agent.id,
            full_name=f"Клиент{marker}",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
            delivery_status=DeliveryStatus.FAILED,
            delivery_error="ConnectionError",
        )
        session.add(application)
        await session.commit()
        agent_id, application_id = agent.id, application.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/admin/applications?q=Клиент{marker}")
            assert response.status_code == 200
            assert f"Клиент{marker}" in response.text
            assert "ConnectionError" in response.text

            filtered = await client.get("/admin/applications?status=failed")
            assert f"Клиент{marker}" in filtered.text

            missed = await client.get("/admin/applications?status=sent")
            assert f"Клиент{marker}" not in missed.text
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id == agent_id))
            await session.commit()


async def test_assign_manager_and_change_processing_status() -> None:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        partner = Agent(email=f"{uuid.uuid4()}@example.test", display_name=f"Партнёр{marker}")
        manager = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Менеджер{marker}",
            role=AgentRole.ADMIN,
        )
        session.add_all([partner, manager])
        await session.flush()
        application = ReferralApplication(
            agent_id=partner.id,
            full_name=f"Клиент{marker}",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.commit()
        partner_id, manager_id, application_id = partner.id, manager.id, application.id

    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            page = await client.get("/admin/applications")
            assert f"Менеджер{marker}" in page.text
            csrf = _csrf_from(page.text)

            manager_response = await client.post(
                f"/admin/applications/{application_id}/manager",
                data={"manager_id": str(manager_id), "csrf": csrf},
                follow_redirects=False,
            )
            assert manager_response.status_code == 303

            status_response = await client.post(
                f"/admin/applications/{application_id}/status",
                data={"processing_status": "in_progress", "csrf": csrf},
                follow_redirects=False,
            )
            assert status_response.status_code == 303

        async with session_factory() as session:
            updated = await session.get(ReferralApplication, application_id)
            assert updated.assigned_manager_id == manager_id
            assert updated.processing_status == ProcessingStatus.IN_PROGRESS
    finally:
        app.dependency_overrides.pop(require_admin, None)
        async with session_factory() as session:
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.execute(delete(Agent).where(Agent.id.in_([partner_id, manager_id])))
            await session.commit()
