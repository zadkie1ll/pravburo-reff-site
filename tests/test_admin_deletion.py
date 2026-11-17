import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentCredential,
    AgentIdentity,
    AgentRole,
    DeliveryStatus,
    EmploymentFormat,
    ExistingClientImport,
    PartnerLevel,
    PartnerLevelMonth,
    PendingPasswordReset,
    PendingRegistration,
    PushSubscription,
    ReferralApplication,
    ReferralLinkVisit,
    Reward,
    RewardStatus,
    RewardType,
)
from sqlalchemy import delete, or_, select

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

BASE = "/api/v1/site/admin/deletions"


@pytest.fixture
async def world():
    marker = uuid.uuid4().hex
    number = uuid.uuid4().int % 10**7
    async with session_factory() as session:
        admin = Agent(email=f"delete-admin-{marker}@example.test", role=AgentRole.ADMIN)
        partner = Agent(
            email=f"delete-partner-{marker}@example.test",
            display_name="Удаляемый партнёр",
            phone_normalized=f"+7999{number:07d}",
            employment_format=EmploymentFormat.INDIVIDUAL,
        )
        other = Agent(
            email=f"delete-other-{marker}@example.test",
            display_name="Другой партнёр",
            employment_format=EmploymentFormat.INDIVIDUAL,
        )
        session.add_all([admin, partner, other])
        await session.flush()
        child = Agent(email=f"delete-child-{marker}@example.test", invited_by_agent_id=partner.id)
        session.add(child)
        await session.flush()
        clients = [
            ReferralApplication(
                agent_id=owner,
                full_name=f"Клиент {i}",
                phone_normalized=f"+7888{(number + i) % 10**7:07d}",
                bitrix_deal_id=str(uuid.uuid4().int % 10**12 + 1),
                delivery_status=DeliveryStatus.SENT,
            )
            for i, owner in enumerate([partner.id, partner.id, other.id])
        ]
        session.add_all(clients)
        await session.flush()
        first = Reward(
            application_id=clients[0].id,
            agent_id=partner.id,
            deal_id=clients[0].bitrix_deal_id,
            reward_type=RewardType.MAIN,
            amount=10000,
            status=RewardStatus.APPROVED,
        )
        second = Reward(
            application_id=clients[1].id,
            agent_id=partner.id,
            deal_id=clients[1].bitrix_deal_id,
            reward_type=RewardType.ADVANCE,
            amount=3000,
            status=RewardStatus.PENDING,
        )
        untouched = Reward(
            application_id=clients[2].id,
            agent_id=other.id,
            deal_id=clients[2].bitrix_deal_id,
            reward_type=RewardType.MAIN,
            amount=10000,
            status=RewardStatus.APPROVED,
        )
        session.add_all([first, second, untouched])
        await session.flush()
        override = Reward(
            application_id=clients[0].id,
            agent_id=other.id,
            deal_id=first.deal_id,
            reward_type=RewardType.OVERRIDE,
            amount=500,
            source_reward_id=first.id,
            network_level=1,
        )
        imported = ExistingClientImport(
            application_id=clients[0].id,
            deal_id=first.deal_id,
            imported_by_agent_id=admin.id,
            current_reward_id=first.id,
            excluded_reward_types=["main"],
        )
        expires = datetime.now(UTC) + timedelta(days=1)
        session.add_all(
            [
                override,
                imported,
                AgentCredential(agent_id=partner.id, password_hash="test-hash"),
                AgentIdentity(agent_id=partner.id, provider="telegram", subject=marker),
                PendingPasswordReset(
                    token=marker,
                    agent_id=partner.id,
                    email=partner.email,
                    code_hash="test",
                    expires_at=expires,
                ),
                PendingRegistration(
                    token=marker,
                    email=partner.email,
                    password_hash="test",
                    code_hash="test",
                    expires_at=expires,
                ),
                PartnerLevelMonth(
                    agent_id=partner.id,
                    year=2026,
                    month=11,
                    contracts_count=1,
                    level=PartnerLevel.START,
                ),
                PushSubscription(
                    agent_id=partner.id,
                    endpoint=f"https://push.test/{marker}",
                    p256dh="test",
                    auth="test",
                ),
                ReferralLinkVisit(agent_id=partner.id),
            ]
        )
        await session.commit()
        ids = [admin.id, partner.id, other.id, child.id]
        state = SimpleNamespace(
            admin=admin,
            partner=partner,
            other=other,
            child=child,
            clients=clients,
            rewards=[first, second, untouched, override],
            ids=ids,
            marker=marker,
        )
    app.dependency_overrides[optional_agent] = lambda: admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            state.client = client
            state.headers = {
                CSRF_HEADER: (await client.get("/api/v1/site/me")).json()["csrf_token"]
            }
            yield state
    finally:
        app.dependency_overrides.pop(optional_agent, None)
        async with session_factory() as session:
            apps = list(
                await session.scalars(
                    select(ReferralApplication.id).where(ReferralApplication.agent_id.in_(ids))
                )
            )
            await session.execute(
                delete(ExistingClientImport).where(ExistingClientImport.application_id.in_(apps))
            )
            await session.execute(
                delete(Reward).where(or_(Reward.application_id.in_(apps), Reward.agent_id.in_(ids)))
            )
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id.in_(apps))
            )
            for model in (PartnerLevelMonth, PushSubscription, ReferralLinkVisit):
                await session.execute(delete(model).where(model.agent_id.in_(ids)))
            await session.execute(
                delete(PendingRegistration).where(
                    PendingRegistration.email.like(f"%{marker}@example.test")
                )
            )
            await session.execute(delete(Agent).where(Agent.id.in_(ids)))
            await session.commit()
        await engine.dispose()


async def remove(w, kind, record_id, token=None):
    url = f"{BASE}/{kind}/{record_id}"
    if token is None:
        response = await w.client.get(url)
        assert response.status_code == 200, response.text
        token = response.json()["token"]
    return await w.client.request("DELETE", url, headers=w.headers, json={"token": token})


async def test_client_delete_removes_its_rewards_and_import_but_preserves_partner_and_others(
    world, monkeypatch
):
    w = world
    target = w.clients[0]
    response = await remove(w, "clients", target.id)
    assert response.status_code == 200, response.text
    async with session_factory() as session:
        assert await session.get(ReferralApplication, target.id) is None
        assert await session.get(ExistingClientImport, target.id) is None
        assert await session.get(Reward, w.rewards[0].id) is None
        assert await session.get(Reward, w.rewards[3].id) is None
        assert await session.get(Agent, w.partner.id) is not None
        assert await session.get(ReferralApplication, w.clients[1].id) is not None
        assert await session.get(Reward, w.rewards[2].id) is not None

    async def snapshot(self, deal_id):
        return dict(
            deal_id=deal_id,
            full_name=target.full_name,
            phone=target.phone_normalized,
            category_id=2,
            stage_code="C2:NEW",
            first_payment="0",
        )

    monkeypatch.setattr("src.web.routes.api_admin_clients.CRMClient.get_existing_client", snapshot)
    again = await w.client.post(
        "/api/v1/site/admin/clients",
        headers=w.headers,
        json=dict(
            agent_id=w.partner.id,
            deal_id=target.bitrix_deal_id,
            full_name=target.full_name,
            phone=target.phone_normalized,
        ),
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] != target.id


async def test_partner_delete_cascades_owned_clients_and_releases_login_contacts(world):
    w = world
    preview = (await w.client.get(f"{BASE}/partners/{w.partner.id}")).json()
    assert preview["client_count"] == 2
    assert preview["invited_partner_count"] == 1
    response = await remove(w, "partners", w.partner.id, preview["token"])
    assert response.status_code == 200, response.text
    async with session_factory() as session:
        assert await session.get(Agent, w.partner.id) is None
        assert await session.get(AgentCredential, w.partner.id) is None
        assert await session.get(PendingPasswordReset, w.marker) is None
        assert await session.get(PendingRegistration, w.marker) is None
        assert await session.get(ReferralApplication, w.clients[0].id) is None
        assert await session.get(ReferralApplication, w.clients[1].id) is None
        assert await session.get(Reward, w.rewards[3].id) is None
        assert await session.get(Reward, w.rewards[2].id) is not None
        child = await session.get(Agent, w.child.id)
        assert child is not None and child.invited_by_agent_id is None
        assert await session.get(ReferralApplication, w.clients[2].id) is not None
    created = await w.client.post(
        "/api/v1/site/admin/partners",
        headers=w.headers,
        json=dict(
            display_name="Создан заново",
            phone=w.partner.phone_normalized,
            email=w.partner.email,
            employment_format="individual",
            payout_details="Тестовые реквизиты",
            inn="",
            admin_note="",
        ),
    )
    assert created.status_code == 201, created.text
    w.ids.append(created.json()["id"])


@pytest.mark.parametrize("kind", ["clients", "partners"])
async def test_paid_reward_prevents_deletion_even_if_payment_happened_after_preview(world, kind):
    w = world
    record_id = w.clients[0].id if kind == "clients" else w.partner.id
    preview = (await w.client.get(f"{BASE}/{kind}/{record_id}")).json()
    async with session_factory() as session:
        row = await session.get(Reward, w.rewards[3].id)
        row.paid_at = datetime.now(UTC)
        await session.commit()
    response = await remove(w, kind, record_id, preview["token"])
    assert response.status_code == 409
    assert "выплат" in response.json()["error"]["message"]
    async with session_factory() as session:
        assert await session.get(Agent, w.partner.id) is not None
        assert await session.get(ReferralApplication, w.clients[0].id) is not None
        assert await session.get(Reward, w.rewards[0].id) is not None


async def test_historical_payment_prevents_deletion(world):
    w = world
    async with session_factory() as session:
        record = await session.get(ExistingClientImport, w.clients[0].id)
        record.workflow_data = {"input": {"advance_paid_on": "2026-10-16"}}
        await session.commit()
    preview = (await w.client.get(f"{BASE}/clients/{w.clients[0].id}")).json()
    assert preview["can_delete"] is False
    assert (await remove(w, "clients", w.clients[0].id, preview["token"])).status_code == 409


async def test_stale_confirmation_cannot_delete_newly_added_clients(world):
    w = world
    preview = (await w.client.get(f"{BASE}/partners/{w.partner.id}")).json()
    async with session_factory() as session:
        session.add(
            ReferralApplication(
                agent_id=w.partner.id,
                full_name="Добавлен после подтверждения",
                phone_normalized="+70000000000",
            )
        )
        await session.commit()
    assert (await remove(w, "partners", w.partner.id, preview["token"])).status_code == 409
    async with session_factory() as session:
        assert await session.get(Agent, w.partner.id) is not None
        assert await session.get(ReferralApplication, w.clients[0].id) is not None


async def test_authorization_csrf_and_admin_account_protection(world):
    w = world
    url = f"{BASE}/partners/{w.partner.id}"
    preview = (await w.client.get(url)).json()
    assert (
        await w.client.request("DELETE", url, json={"token": preview["token"]})
    ).status_code == 403
    admin_preview = (await w.client.get(f"{BASE}/partners/{w.admin.id}")).json()
    assert admin_preview["can_delete"] is False
    assert (await remove(w, "partners", w.admin.id, admin_preview["token"])).status_code == 409
    app.dependency_overrides[optional_agent] = lambda: w.other
    assert (await w.client.get(url)).status_code == 403
    assert (
        await w.client.request("DELETE", url, headers=w.headers, json={"token": preview["token"]})
    ).status_code == 403
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await w.client.get(url)).status_code == 401


async def test_partner_delete_detaches_only_its_unpaid_curator_line_on_other_client(world):
    w = world
    async with session_factory() as session:
        curator_reward = Reward(
            agent_id=w.partner.id,
            application_id=w.clients[2].id,
            deal_id=w.clients[2].bitrix_deal_id,
            reward_type=RewardType.CURATOR,
            amount=2500,
            status=RewardStatus.APPROVED,
        )
        session.add(curator_reward)
        await session.flush()
        session.add(
            ExistingClientImport(
                application_id=w.clients[2].id,
                deal_id=w.clients[2].bitrix_deal_id,
                imported_by_agent_id=w.admin.id,
                excluded_reward_types=["main"],
                workflow_data={
                    "version": 1,
                    "curator_id": w.partner.id,
                    "input": {
                        "main_amount": "10000",
                        "curator_amount": "2500",
                        "curator_paid_on": None,
                    },
                    "reward_ids": {"main": w.rewards[2].id, "curator": curator_reward.id},
                },
            )
        )
        await session.commit()
        curator_reward_id = curator_reward.id
    response = await remove(w, "partners", w.partner.id)
    assert response.status_code == 200, response.text
    async with session_factory() as session:
        record = await session.get(ExistingClientImport, w.clients[2].id)
        assert record.workflow_data["curator_id"] is None
        assert record.workflow_data["input"]["main_amount"] == "10000"
        assert record.workflow_data["input"]["curator_amount"] == "0"
        assert record.workflow_data["reward_ids"] == {"main": w.rewards[2].id}
        assert await session.get(Reward, curator_reward_id) is None
        assert await session.get(Reward, w.rewards[2].id) is not None
