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


@pytest.fixture
async def workflow_world(world, monkeypatch):
    async def names(self):
        return {"C2:UC_MYA2I0": "Депозит"}

    monkeypatch.setattr(CRMClient, "get_deal_stage_labels", names)

    async def quiet_notice(*args):
        return None

    monkeypatch.setattr("src.web.routes.api_client_workflow._tell_partner", quiet_notice)
    return world


def settlement_body():
    return dict(
        contract_date="2026-10-10", first_payment="8000", advance_amount="3000", main_amount="10000"
    )


async def create_settlement(world, **changes):
    client, ids, snapshot, headers = world
    response = await client.post(
        "/api/v1/site/admin/clients",
        headers=headers,
        json=dict(
            agent_id=ids[1],
            deal_id=snapshot["deal_id"],
            full_name=snapshot["full_name"],
            phone=snapshot["phone"],
            workflow={**settlement_body(), **changes},
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_structured_import_payment_history_is_not_accrued_again(workflow_world):
    client, _, _, headers = workflow_world
    app_id = await create_settlement(
        workflow_world,
        advance_paid_on="2026-10-16",
        deposit_paid_on="2026-11-12",
        paid_in_full=True,
    )
    url = f"/api/v1/site/admin/client-workflows/{app_id}"
    data = (await client.get(url)).json()["workflow"]
    assert data["outstanding"] == "13000.00"
    assert data["stages"][0]["historical"] is True
    assert data["stages"][0]["reward_id"] is None
    assert data["stages"][1]["due_on"] == "2026-12-03"
    async with session_factory() as session:
        rewards = (
            await session.scalars(select(Reward).where(Reward.application_id == app_id))
        ).all()
        assert {r.reward_type.value for r in rewards} == {"main", "bonus_full_payment"}
    # Saving twice is versioned and never duplicates payouts.
    body = {**data["input"], "version": data["version"]}
    saved = await client.post(url, headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert (await client.post(url, headers=headers, json=body)).status_code == 409
    current = saved.json()
    paid = await client.post(
        url + "/main/pay",
        headers=headers,
        json={"version": current["version"], "paid_on": "2026-11-13"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["outstanding"] == "0"
    assert paid.json()["status_label"] == "Всё выплачено"
    repeated = await client.post(
        url + "/main/pay",
        headers=headers,
        json={"version": paid.json()["version"], "paid_on": "2026-11-13"},
    )
    assert repeated.status_code == 409
    changed = {**paid.json()["input"], "version": paid.json()["version"], "main_amount": "15000"}
    assert (await client.post(url, headers=headers, json=changed)).status_code == 409


async def test_threshold_creates_one_advance_then_one_main(workflow_world):
    client, _, _, headers = workflow_world
    app_id = await create_settlement(workflow_world, first_payment="7999.99")
    url = f"/api/v1/site/admin/client-workflows/{app_id}"
    data = (await client.get(url)).json()["workflow"]
    assert data["stages"][0]["status"] == "waiting"
    assert data["outstanding"] == "0"
    response = await client.post(
        url,
        headers=headers,
        json={**data["input"], "version": data["version"], "first_payment": "8000"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["outstanding"] == "3000.00"
    response = await client.post(
        url,
        headers=headers,
        json={**data["input"], "version": data["version"], "deposit_paid_on": "2026-11-12"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["outstanding"] == "13000.00"
    # The old singular editor cannot overwrite this settlement.
    response = await client.post(
        f"/api/v1/site/admin/clients/{app_id}/payout",
        headers=headers,
        json={"current_amount": "1", "payout_due_date": "2026-12-01"},
    )
    assert response.status_code == 409


async def test_curator_is_a_separate_recipient_and_history_can_be_complete(workflow_world):
    client, ids, _, headers = workflow_world
    async with session_factory() as session:
        partner = await session.get(Agent, ids[1])
        partner.invited_by_agent_id = ids[2]
        await session.commit()
    app_id = await create_settlement(
        workflow_world,
        advance_paid_on="2026-10-16",
        deposit_paid_on="2026-11-12",
        main_paid_on="2026-11-13",
        curator_amount="2500",
    )
    url = f"/api/v1/site/admin/client-workflows/{app_id}"
    data = (await client.get(url)).json()["workflow"]
    assert data["outstanding"] == "2500.00"
    async with session_factory() as session:
        rewards = (
            await session.scalars(select(Reward).where(Reward.application_id == app_id))
        ).all()
        assert len(rewards) == 1
        assert rewards[0].agent_id == ids[2]
        assert rewards[0].reward_type.value == "curator"
    assert (
        await client.post(
            url + "/curator/pay", json={"version": data["version"], "paid_on": "2026-11-13"}
        )
    ).status_code == 403
    paid = await client.post(
        url + "/curator/pay",
        headers=headers,
        json={"version": data["version"], "paid_on": "2026-11-13"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status_label"] == "Всё выплачено"


async def test_complete_history_does_not_look_like_a_new_unpaid_contract(workflow_world):
    from src.services.payouts import PayoutFilters, get_payout_rows

    client, ids, _, _ = workflow_world
    app_id = await create_settlement(
        workflow_world,
        advance_paid_on="2026-10-16",
        deposit_paid_on="2026-11-12",
        main_paid_on="2026-11-13",
    )
    data = (await client.get(f"/api/v1/site/admin/client-workflows/{app_id}")).json()["workflow"]
    assert data["outstanding"] == "0"
    assert data["status_label"] == "Всё выплачено"
    assert data["next_due_on"] is None
    async with session_factory() as session:
        assert await get_payout_rows(session, ids[1], PayoutFilters()) == []


async def test_client_can_be_bound_before_contract_then_completed_later(workflow_world):
    client, _, _, headers = workflow_world
    app_id = await create_settlement(
        workflow_world, contract_date=None, contract_status="not_signed", first_payment="8000"
    )
    url = f"/api/v1/site/admin/client-workflows/{app_id}"
    data = (await client.get(url)).json()["workflow"]
    assert data["status_label"] == "Договор не заключён"
    assert data["outstanding"] == "0"
    assert data["next_due_on"] is None
    assert all(stage["reward_id"] is None for stage in data["stages"])
    assert (
        await client.post(
            url + "/advance/pay",
            headers=headers,
            json={
                "version": data["version"],
                "paid_on": "2026-11-13",
            },
        )
    ).status_code == 409
    response = await client.post(
        url,
        headers=headers,
        json={
            **data["input"],
            "version": data["version"],
            "contract_status": "date_unknown",
            "deposit_paid_on": "2026-11-12",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status_label"] == "Договор подписан — уточните дату"
    assert data["outstanding"] == "0"
    response = await client.post(
        url,
        headers=headers,
        json={
            **data["input"],
            "version": data["version"],
            "contract_status": "signed",
            "contract_date": "2026-10-10",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["outstanding"] == "13000.00"
    assert data["stages"][0]["due_on"] == "2026-10-16"
    assert data["stages"][1]["due_on"] == "2026-12-03"
    response = await client.post(
        url,
        headers=headers,
        json={
            **data["input"],
            "version": data["version"],
            "contract_status": "date_unknown",
            "contract_date": None,
        },
    )
    assert response.status_code == 409
