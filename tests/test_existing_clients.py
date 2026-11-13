import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentRole,
    ExistingClientImport,
    ReferralApplication,
    Reward,
)
from sqlalchemy import delete, select

from src.main import app
from src.services.existing_clients import accounted_milestones, current_balance
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent
from src.web.routes.api_admin_clients import CRMClient


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        ({"category_id": 0, "stage_code": "NEW", "first_payment": "9000"}, []),
        ({"category_id": 2, "stage_code": "C2:NEW", "first_payment": "7999"}, []),
        ({"category_id": 2, "stage_code": "C2:NEW", "first_payment": "8000"}, ["advance"]),
        (
            {
                "category_id": 2,
                "stage_code": "C2:UC_7TR7XT",
                "first_payment": "10000",
                "paid_in_full": True,
            },
            ["advance", "main", "bonus_full_payment"],
        ),
    ],
)
def test_import_snapshots_already_earned_milestones(snapshot, expected):
    assert accounted_milestones(snapshot) == expected


@pytest.mark.parametrize(
    "amount", [Decimal("-1"), Decimal("0"), Decimal("0.001"), Decimal("NaN"), Decimal("Infinity")]
)
def test_invalid_current_balance_is_refused(amount):
    with pytest.raises(ValueError):
        current_balance(amount)


@pytest.fixture
async def world(monkeypatch):
    marker = uuid.uuid4().hex
    async with session_factory() as session:
        admin = Agent(email=f"admin-{marker}@example.test", role=AgentRole.ADMIN)
        partner = Agent(email=f"partner-{marker}@example.test", display_name="Партнёр")
        other = Agent(email=f"other-{marker}@example.test", display_name="Другой партнёр")
        session.add_all([admin, partner, other])
        await session.commit()
        ids = [admin.id, partner.id, other.id]
    snapshot = {
        "deal_id": str(uuid.uuid4().int % 10**12 + 1),
        "full_name": f"Клиент{marker}",
        "phone": f"+7999{uuid.uuid4().int % 10**7:07d}",
        "category_id": 2,
        "stage_code": "C2:UC_MYA2I0",
        "first_payment": "9000",
        "paid_in_full": False,
        "attributed_agent_id": None,
        "attributed_application_id": None,
    }

    async def get_existing(self, deal_id):
        assert deal_id == snapshot["deal_id"]
        return dict(snapshot)

    monkeypatch.setattr(CRMClient, "get_existing_client", get_existing)
    app.dependency_overrides[optional_agent] = lambda: admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            csrf = (await client.get("/api/v1/site/me")).json()["csrf_token"]
            yield client, ids, snapshot, {CSRF_HEADER: csrf}
    finally:
        app.dependency_overrides.pop(optional_agent, None)
        async with session_factory() as session:
            apps = list(
                (
                    await session.scalars(
                        select(ReferralApplication.id).where(ReferralApplication.agent_id.in_(ids))
                    )
                ).all()
            )
            await session.execute(
                delete(ExistingClientImport).where(ExistingClientImport.application_id.in_(apps))
            )
            await session.execute(delete(Reward).where(Reward.application_id.in_(apps)))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(apps))
            )
            await session.execute(delete(Agent).where(Agent.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def test_import_keeps_current_balance_without_new_application_or_duplicate(world):
    client, ids, snapshot, headers = world
    body = {
        "agent_id": ids[1],
        "deal_id": snapshot["deal_id"],
        "full_name": snapshot["full_name"],
        "phone": snapshot["phone"],
        "current_amount": "1700.50",
        "admin_note": "Из таблицы бухгалтера",
    }
    response = await client.post("/api/v1/site/admin/clients", json=body, headers=headers)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["current_amount"] == "1700.50"
    assert result["current_status"] == "pending"
    repeated = await client.post("/api/v1/site/admin/clients", json=body, headers=headers)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == result["id"]
    async with session_factory() as session:
        imported = await session.get(ExistingClientImport, result["id"])
        assert set(imported.excluded_reward_types) == {"advance", "main"}
        rewards = (
            await session.scalars(select(Reward).where(Reward.application_id == result["id"]))
        ).all()
        assert len(rewards) == 1
        assert rewards[0].amount == Decimal("1700.50")
    apps = (
        await client.get("/api/v1/site/admin/applications", params={"q": snapshot["full_name"]})
    ).json()
    assert apps["total_count"] == 0
    clients = (await client.get("/api/v1/site/admin/clients", params={"agent_id": ids[1]})).json()
    assert clients["total_count"] == 1
    conflict = await client.post(
        "/api/v1/site/admin/clients", json={**body, "agent_id": ids[2]}, headers=headers
    )
    assert conflict.status_code == 409


async def test_import_checks_csrf_and_existing_bitrix_marker(world):
    client, ids, snapshot, headers = world
    body = {
        "agent_id": ids[1],
        "deal_id": snapshot["deal_id"],
        "full_name": snapshot["full_name"],
        "phone": snapshot["phone"],
    }
    assert (await client.post("/api/v1/site/admin/clients", json=body)).status_code == 403
    snapshot["attributed_agent_id"] = ids[2]
    assert (
        await client.post("/api/v1/site/admin/clients", json=body, headers=headers)
    ).status_code == 409
