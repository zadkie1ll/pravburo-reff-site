import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import (
    Agent,
    AgentCredential,
    AgentRole,
    EmploymentFormat,
    PendingPasswordReset,
    ReferralApplication,
    Reward,
    RewardStatus,
)
from sqlalchemy import delete, or_, select

from src.core.auth import begin_password_reset, confirm_password_reset
from src.core.security import hash_password, verify_password
from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent

URL = "/api/v1/site/admin/partners"
PROFILE = {
    "display_name": "Анна Партнёрова",
    "phone": "",
    "employment_format": "individual",
    "payout_details": "Карта 2200",
    "inn": "",
    "admin_note": "Тест",
}


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.fixture
async def world() -> AsyncIterator[SimpleNamespace]:
    marker = uuid.uuid4().hex
    async with session_factory() as session:
        admin = Agent(email=f"admin-{marker}@example.test", role=AgentRole.ADMIN)
        session.add(admin)
        await session.flush()
        partner = Agent(
            email=f"partner-{marker}@example.test",
            display_name="До изменения",
            employment_format=EmploymentFormat.INDIVIDUAL,
            invited_by_agent_id=admin.id,
            payout_details="Старые реквизиты",
        )
        session.add(partner)
        await session.flush()
        session.add(
            AgentCredential(
                agent_id=partner.id, password_hash=hash_password("old-partner-password")
            )
        )
        application = ReferralApplication(
            agent_id=partner.id, full_name="Клиент", phone_normalized="+79991112233"
        )
        session.add(application)
        await session.flush()
        reward = Reward(
            application_id=application.id,
            agent_id=partner.id,
            deal_id=marker,
            status=RewardStatus.APPROVED,
            amount=3000,
        )
        session.add(reward)
        await session.commit()
        ids = (admin.id, partner.id, application.id, reward.id)
    # A real active admin, but no DB-dependent sign-in is necessary for these API tests.
    admin.is_active = True
    app.dependency_overrides[optional_agent] = lambda: admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

            async def post(path, body):
                me = (await client.get("/api/v1/site/me")).json()
                return await client.post(path, json=body, headers={CSRF_HEADER: me["csrf_token"]})

            yield SimpleNamespace(
                client=client,
                post=post,
                admin=admin,
                partner=partner,
                marker=marker,
                email=f"new-{marker}@example.test",
                application_id=ids[2],
                reward_id=ids[3],
            )
    finally:
        app.dependency_overrides.pop(optional_agent, None)
        async with session_factory() as session:
            agent_ids = list(
                (
                    await session.scalars(
                        select(Agent.id).where(
                            or_(
                                Agent.email.like(f"%{marker}@example.test"),
                                Agent.display_name == f"Без почты {marker}",
                            )
                        )
                    )
                ).all()
            )
            await session.execute(delete(Reward).where(Reward.id == ids[3]))
            await session.execute(
                delete(ReferralApplication).where(ReferralApplication.id == ids[2])
            )
            await session.execute(
                delete(PendingPasswordReset).where(PendingPasswordReset.agent_id.in_(agent_ids))
            )
            await session.execute(
                delete(AgentCredential).where(AgentCredential.agent_id.in_(agent_ids))
            )
            # Remove the children before their inviter.
            await session.execute(delete(Agent).where(Agent.id.in_(agent_ids), Agent.id != ids[0]))
            await session.execute(delete(Agent).where(Agent.id == ids[0]))
            await session.commit()


async def test_create_partner_with_profile_and_personal_password_setup(world):
    response = await world.post(URL, {**PROFILE, "email": world.email.upper()})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == world.email
    assert data["display_name"] == PROFILE["display_name"]
    assert data["is_admin"] is False
    async with session_factory() as session:
        agent = await session.get(Agent, data["id"])
        assert agent.role == AgentRole.AGENT
        assert agent.payout_details == PROFILE["payout_details"]
        credential = await session.get(AgentCredential, agent.id)
        password = agent.admin_note.rsplit("Пароль: ", 1)[1]
        assert len(password) == 8
        assert agent.admin_note.startswith(PROFILE["admin_note"] + "\n")
        assert verify_password(password, credential.password_hash)
        pending, code = await begin_password_reset(session, world.email)
        await confirm_password_reset(session, pending.token, code, "own-password-123")
        credential = await session.get(AgentCredential, agent.id)
        assert verify_password("own-password-123", credential.password_hash)


async def test_edit_preserves_attribution_credentials_and_rewards(world):
    before = world.partner
    response = await world.post(
        f"{URL}/{before.id}",
        {
            **PROFILE,
            "phone": "+79992223344",
            "employment_format": "self_employed",
            "inn": "123456789012",
        },
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+79992223344"
    async with session_factory() as session:
        agent = await session.get(Agent, before.id)
        assert agent.display_name == PROFILE["display_name"]
        assert agent.email == before.email
        assert agent.referral_code == before.referral_code
        assert agent.invited_by_agent_id == before.invited_by_agent_id
        assert agent.role == AgentRole.AGENT
        credential = await session.get(AgentCredential, agent.id)
        assert verify_password("old-partner-password", credential.password_hash)
        reward = await session.get(Reward, world.reward_id)
        assert reward.agent_id == agent.id and reward.amount == 3000


@pytest.mark.parametrize(
    "patch",
    [
        {"display_name": "  "},
        {"payout_details": "  "},
        {"employment_format": "self_employed", "inn": ""},
        {"phone": "wrong"},
    ],
)
async def test_validation_does_not_create_an_incomplete_partner(world, patch):
    response = await world.post(URL, {**PROFILE, "email": world.email, **patch})
    assert response.status_code == 400
    async with session_factory() as session:
        assert await session.scalar(select(Agent.id).where(Agent.email == world.email)) is None


async def test_duplicate_email_does_not_take_over_an_existing_account(world):
    response = await world.post(URL, {**PROFILE, "email": world.partner.email.upper()})
    assert response.status_code == 400
    assert "почта" in response.json()["error"]["message"].lower()


async def test_duplicate_phone_is_refused(world):
    assert (
        await world.post(URL, {**PROFILE, "email": world.email, "phone": "+79992223344"})
    ).status_code == 201
    response = await world.post(f"{URL}/{world.partner.id}", {**PROFILE, "phone": "+79992223344"})
    assert response.status_code == 400


async def test_no_admin_role_or_email_changes_through_profile_endpoint(world):
    assert (
        await world.post(URL, {**PROFILE, "email": world.email, "role": "admin"})
    ).status_code == 422
    assert (
        await world.post(f"{URL}/{world.partner.id}", {**PROFILE, "email": world.email})
    ).status_code == 422
    assert (await world.post(f"{URL}/{world.admin.id}", PROFILE)).status_code == 400


async def test_permissions_and_csrf(world):
    assert (await world.client.post(URL, json={**PROFILE, "email": world.email})).status_code == 403
    app.dependency_overrides[optional_agent] = lambda: None
    assert (await world.post(URL, {**PROFILE, "email": world.email})).status_code == 401
    app.dependency_overrides[optional_agent] = lambda: world.partner
    assert (await world.post(f"{URL}/{world.partner.id}", PROFILE)).status_code == 403


async def test_new_partner_can_be_linked_to_an_existing_client_application(world):
    response = await world.post(URL, {**PROFILE, "email": world.email, "phone": "+79991112233"})
    assert response.status_code == 201
    async with session_factory() as session:
        agent = await session.get(Agent, response.json()["id"])
        assert agent.invited_by_agent_id == world.partner.id


@pytest.mark.parametrize("email_fields", [{}, {"email": ""}, {"email": "   "}, {"email": None}])
async def test_admin_can_create_multiple_partners_without_email(world, email_fields):
    for _ in range(2):
        response = await world.post(
            URL, {**PROFILE, "display_name": f"Без почты {world.marker}", **email_fields}
        )
        assert response.status_code == 201
        assert response.json()["email"] is None
        async with session_factory() as session:
            agent = await session.get(Agent, response.json()["id"])
            assert agent.email is None
            assert agent.role == AgentRole.AGENT
            assert agent.payout_details == PROFILE["payout_details"]


async def test_nonempty_invalid_email_is_still_refused(world):
    response = await world.post(URL, {**PROFILE, "email": "not-an-email"})
    assert response.status_code == 400
