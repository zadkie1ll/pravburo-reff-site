import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    DeliveryStatus,
    EmploymentFormat,
    ProcessingStatus,
    ReferralApplication,
)
from sqlalchemy import delete

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

URL = "/api/v1/site/admin/applications"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@dataclass
class Setup:
    client: AsyncClient
    admin: Agent
    partner_id: int
    application_id: int
    marker: str

    async def post(self, path: str, body: dict):
        me = (await self.client.get("/api/v1/site/me")).json()
        return await self.client.post(path, json=body, headers={CSRF_HEADER: me["csrf_token"]})

    async def db_application(self) -> ReferralApplication:
        async with session_factory() as session:
            return await session.get(ReferralApplication, self.application_id)


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        partner = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Партнёр{marker}",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        admin = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Админ{marker}",
            role=AgentRole.ADMIN,
        )
        session.add_all([partner, admin])
        await session.flush()
        application = ReferralApplication(
            agent_id=partner.id,
            full_name=f"Клиент{marker}",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
            city="Казань",
            delivery_status=DeliveryStatus.FAILED,
            delivery_error="ConnectionError",
        )
        session.add(application)
        await session.commit()
        ids = (partner.id, admin.id, application.id)
    async with session_factory() as session:
        admin_row = await session.get(Agent, ids[1])
    app.dependency_overrides[optional_agent] = lambda: admin_row
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield Setup(
            client=client,
            admin=admin_row,
            partner_id=ids[0],
            application_id=ids[2],
            marker=marker,
        )
    app.dependency_overrides.pop(optional_agent, None)
    async with session_factory() as session:
        await session.execute(delete(ReferralApplication).where(ReferralApplication.id == ids[2]))
        await session.execute(delete(Agent).where(Agent.id.in_([ids[0], ids[1]])))
        await session.commit()


async def test_only_admins_may_list(setup: Setup) -> None:
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await setup.client.get(URL)).status_code == 401
    partner = Agent(
        id=setup.partner_id,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )
    app.dependency_overrides[optional_agent] = lambda: partner

    assert (await setup.client.get(URL)).status_code == 403


async def test_list_finds_an_application_and_offers_the_options(setup: Setup) -> None:
    body = (await setup.client.get(URL, params={"q": setup.marker})).json()

    assert body["total_count"] == 1
    row = body["rows"][0]
    assert row["client_name"] == f"Клиент{setup.marker}"
    assert row["agent_name"] == f"Партнёр{setup.marker}"
    assert row["delivery_label"] == "Ошибка отправки"
    assert row["delivery_error"] == "ConnectionError"
    assert row["processing_status"] == "new"
    assert row["assigned_manager_id"] is None
    assert {o["value"] for o in body["delivery_statuses"]} == {"pending", "sent", "failed"}
    assert {o["value"] for o in body["processing_statuses"]} == {"new", "in_progress", "closed"}
    assert setup.admin.id in {manager["id"] for manager in body["managers"]}


async def test_list_filters_by_delivery_status(setup: Setup) -> None:
    failed = await setup.client.get(URL, params={"q": setup.marker, "status": "failed"})
    sent = await setup.client.get(URL, params={"q": setup.marker, "status": "sent"})

    assert failed.json()["total_count"] == 1
    assert sent.json()["total_count"] == 0
    assert sent.json()["rows"] == []


async def test_unknown_delivery_status_is_a_validation_error(setup: Setup) -> None:
    response = await setup.client.get(URL, params={"status": "nonsense"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_page_beyond_the_end_is_clamped(setup: Setup) -> None:
    body = (await setup.client.get(URL, params={"q": setup.marker, "page": 99})).json()

    assert body["page"] == 1
    assert body["total_pages"] == 1


async def test_processing_status_is_saved(setup: Setup) -> None:
    response = await setup.post(
        f"{URL}/{setup.application_id}/status", {"processing_status": "in_progress"}
    )

    assert response.status_code == 200
    assert (await setup.db_application()).processing_status == ProcessingStatus.IN_PROGRESS


async def test_invalid_processing_status_is_refused(setup: Setup) -> None:
    response = await setup.post(
        f"{URL}/{setup.application_id}/status", {"processing_status": "archived"}
    )

    assert response.status_code == 422
    assert (await setup.db_application()).processing_status == ProcessingStatus.NEW


async def test_unknown_application_is_a_404(setup: Setup) -> None:
    status = await setup.post(f"{URL}/999999999/status", {"processing_status": "closed"})
    manager = await setup.post(f"{URL}/999999999/manager", {"manager_id": None})

    assert status.status_code == manager.status_code == 404


async def test_changes_require_csrf(setup: Setup) -> None:
    response = await setup.client.post(
        f"{URL}/{setup.application_id}/status", json={"processing_status": "closed"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert (await setup.db_application()).processing_status == ProcessingStatus.NEW


async def test_manager_can_be_assigned_and_cleared(setup: Setup) -> None:
    assign = await setup.post(
        f"{URL}/{setup.application_id}/manager", {"manager_id": setup.admin.id}
    )
    assert assign.status_code == 200
    assert (await setup.db_application()).assigned_manager_id == setup.admin.id

    clear = await setup.post(f"{URL}/{setup.application_id}/manager", {"manager_id": None})
    assert clear.status_code == 200
    assert (await setup.db_application()).assigned_manager_id is None


async def test_only_an_admin_can_be_a_manager(setup: Setup) -> None:
    response = await setup.post(
        f"{URL}/{setup.application_id}/manager", {"manager_id": setup.partner_id}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_manager"
    assert (await setup.db_application()).assigned_manager_id is None
