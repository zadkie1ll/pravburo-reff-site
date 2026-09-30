import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from sqlalchemy import delete

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

URL = "/api/v1/site/admin/partners"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@dataclass
class Setup:
    client: AsyncClient
    admin_id: int
    partner_id: int
    marker: str

    async def post(self, path: str, body: dict | None = None):
        me = (await self.client.get("/api/v1/site/me")).json()
        return await self.client.post(
            path, json=body or {}, headers={CSRF_HEADER: me["csrf_token"]}
        )

    async def agent(self, agent_id: int | None = None) -> Agent:
        async with session_factory() as session:
            return await session.get(Agent, agent_id or self.partner_id)


@pytest.fixture
async def setup() -> AsyncIterator[Setup]:
    marker = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        partner = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Партнёр{marker}",
            payout_details="Карта 1111",
            employment_format=EmploymentFormat.SELF_EMPLOYED,
        )
        admin = Agent(
            email=f"{uuid.uuid4()}@example.test",
            display_name=f"Админ{marker}",
            role=AgentRole.ADMIN,
        )
        session.add_all([partner, admin])
        await session.commit()
        partner_id, admin_id = partner.id, admin.id
    async with session_factory() as session:
        admin_row = await session.get(Agent, admin_id)
    app.dependency_overrides[optional_agent] = lambda: admin_row
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield Setup(client=client, admin_id=admin_id, partner_id=partner_id, marker=marker)
    app.dependency_overrides.pop(optional_agent, None)
    async with session_factory() as session:
        await session.execute(delete(Agent).where(Agent.id.in_([partner_id, admin_id])))
        await session.commit()


async def test_only_admins_may_use_it(setup: Setup) -> None:
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await setup.client.get(URL)).status_code == 401
    partner = await setup.agent()
    app.dependency_overrides[optional_agent] = lambda: partner

    assert (await setup.client.get(URL)).status_code == 403


async def test_list_shows_a_partner_with_counts_and_options(setup: Setup) -> None:
    body = (await setup.client.get(URL, params={"q": setup.marker})).json()

    partner = next(row for row in body["rows"] if row["id"] == setup.partner_id)
    assert partner["display_name"] == f"Партнёр{setup.marker}"
    assert partner["is_active"] is True
    assert partner["is_admin"] is False
    assert partner["client_count"] == 0
    assert partner["total_paid"] == "0"
    assert partner["payout_details"] == "Карта 1111"
    assert {o["value"] for o in body["statuses"]} == {"active", "blocked"}
    admin = next(row for row in body["rows"] if row["id"] == setup.admin_id)
    assert admin["is_admin"] is True


async def test_list_filters_by_status_and_rejects_unknown_ones(setup: Setup) -> None:
    active = await setup.client.get(URL, params={"q": setup.marker, "status": "active"})
    blocked = await setup.client.get(URL, params={"q": setup.marker, "status": "blocked"})
    unknown = await setup.client.get(URL, params={"status": "nonsense"})

    assert active.json()["total_count"] == 2
    assert blocked.json()["total_count"] == 0
    assert unknown.status_code == 422


async def test_note_is_saved_trimmed_and_cleared_when_empty(setup: Setup) -> None:
    saved = await setup.post(f"{URL}/{setup.partner_id}/note", {"note": "  звонить после 18  "})
    assert saved.status_code == 200
    assert (await setup.agent()).admin_note == "звонить после 18"

    await setup.post(f"{URL}/{setup.partner_id}/note", {"note": "   "})
    assert (await setup.agent()).admin_note is None


async def test_blocking_needs_a_reason_and_stores_it(setup: Setup) -> None:
    empty = await setup.post(f"{URL}/{setup.partner_id}/block", {"reason": "   "})
    assert empty.status_code == 400
    assert "reason" in empty.json()["error"]["fields"]
    assert (await setup.agent()).is_active is True

    blocked = await setup.post(f"{URL}/{setup.partner_id}/block", {"reason": " Мошенничество "})
    assert blocked.status_code == 200
    partner = await setup.agent()
    assert partner.is_active is False
    assert partner.blocked_reason == "Мошенничество"


async def test_an_admin_cannot_be_blocked(setup: Setup) -> None:
    response = await setup.post(f"{URL}/{setup.admin_id}/block", {"reason": "Нельзя"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "cannot_block_admin"
    assert (await setup.agent(setup.admin_id)).is_active is True


async def test_unblocking_restores_access_and_clears_the_reason(setup: Setup) -> None:
    await setup.post(f"{URL}/{setup.partner_id}/block", {"reason": "Мошенничество"})

    response = await setup.post(f"{URL}/{setup.partner_id}/unblock")

    assert response.status_code == 200
    partner = await setup.agent()
    assert partner.is_active is True
    assert partner.blocked_reason is None


async def test_unknown_partner_is_a_404(setup: Setup) -> None:
    for action, body in (("note", {"note": "x"}), ("block", {"reason": "x"}), ("unblock", None)):
        response = await setup.post(f"{URL}/999999999/{action}", body)
        assert response.status_code == 404, action


async def test_changes_require_csrf(setup: Setup) -> None:
    response = await setup.client.post(f"{URL}/{setup.partner_id}/block", json={"reason": "x"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert (await setup.agent()).is_active is True


async def test_list_counts_a_partners_clients_and_sums_what_was_paid(setup: Setup) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    from pravburo_ref_common.models import ReferralApplication, Reward, RewardStatus, RewardType

    async with session_factory() as session:
        application = ReferralApplication(
            agent_id=setup.partner_id,
            full_name="Клиент Партнёра",
            phone_normalized=f"+7999{uuid.uuid4().int % 10**7:07d}",
        )
        session.add(application)
        await session.flush()
        session.add_all(
            [
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=application.id,
                    agent_id=setup.partner_id,
                    reward_type=RewardType.ADVANCE,
                    status=RewardStatus.APPROVED,
                    amount=Decimal("3000.00"),
                    paid_at=datetime.now(UTC),
                ),
                # Approved but not paid yet: must not count as paid.
                Reward(
                    deal_id=str(uuid.uuid4()),
                    application_id=application.id,
                    agent_id=setup.partner_id,
                    reward_type=RewardType.MAIN,
                    status=RewardStatus.APPROVED,
                    amount=Decimal("10000.00"),
                ),
            ]
        )
        await session.commit()
        application_id = application.id

    try:
        body = (await setup.client.get(URL, params={"q": setup.marker})).json()
    finally:
        async with session_factory() as session:
            await session.execute(delete(Reward).where(Reward.application_id == application_id))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == application_id)
            )
            await session.commit()

    partner = next(row for row in body["rows"] if row["id"] == setup.partner_id)
    assert partner["client_count"] == 1
    assert partner["total_paid"] == "3000.00"
