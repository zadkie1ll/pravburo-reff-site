import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, DeliveryStatus, ReferralApplication
from sqlalchemy import delete

from src.main import app
from src.web.dependencies import require_admin

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


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
