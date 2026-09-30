import base64
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentCredential, EmploymentFormat
from sqlalchemy import delete, select

from src.core.security import hash_password
from src.main import app
from src.services.protection import login_rate_limiter
from src.web.api_dependencies import CSRF_HEADER
from src.web.routes import api_profile

PASSWORD = "current-pass-1"
URL = "/api/v1/site/profile"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@dataclass
class Partner:
    client: AsyncClient
    agent_id: int
    email: str
    codes: list[str]

    async def post(self, path: str, body: dict):
        me = (await self.client.get("/api/v1/site/me")).json()
        return await self.client.post(path, json=body, headers={CSRF_HEADER: me["csrf_token"]})

    async def db_agent(self) -> Agent:
        async with session_factory() as session:
            return await session.get(Agent, self.agent_id)

    async def db_email(self) -> str | None:
        async with session_factory() as session:
            return await session.scalar(select(Agent.email).where(Agent.id == self.agent_id))


async def _create_agent(*, with_format: bool = True) -> tuple[int, str]:
    email = f"{uuid.uuid4()}@example.test"
    async with session_factory() as session:
        agent = Agent(
            email=email,
            display_name="Профиль Тестов",
            employment_format=EmploymentFormat.SELF_EMPLOYED if with_format else None,
        )
        session.add(agent)
        await session.flush()
        session.add(AgentCredential(agent_id=agent.id, password_hash=hash_password(PASSWORD)))
        await session.commit()
        return agent.id, email


async def _delete_agents(*agent_ids: int) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(AgentCredential).where(AgentCredential.agent_id.in_(agent_ids))
        )
        await session.execute(delete(Agent).where(Agent.id.in_(agent_ids)))
        await session.commit()


@pytest.fixture
async def partner(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Partner]:
    """A partner logged in through the real login endpoint (real session cookie)."""
    login_rate_limiter.reset()
    codes: list[str] = []

    async def capture_code(email, code, purpose):
        codes.append(code)

    monkeypatch.setattr(api_profile, "send_code", capture_code)
    agent_id, email = await _create_agent()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        person = Partner(client=client, agent_id=agent_id, email=email, codes=codes)
        login = await person.post("/api/v1/site/auth/login", {"email": email, "password": PASSWORD})
        assert login.status_code == 200
        yield person
    await _delete_agents(agent_id)


async def test_profile_requires_login() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get(URL)).status_code == 401


async def test_profile_shows_the_partners_data(partner: Partner) -> None:
    body = (await partner.client.get(URL)).json()

    assert body["email"] == partner.email
    assert body["display_name"] == "Профиль Тестов"
    assert body["employment_format"] == "self_employed"
    assert body["is_active"] is True
    assert body["pending_email"] == ""
    assert [option["value"] for option in body["employment_formats"]] == [
        "self_employed",
        "individual_entrepreneur",
        "individual",
    ]


async def test_profile_update_saves_and_returns_the_new_data(partner: Partner) -> None:
    response = await partner.post(
        URL,
        {
            "display_name": "Новое Имя",
            "phone": "",
            "employment_format": "individual",
            "payout_details": "Карта 1234",
            "inn": "",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Новое Имя"
    assert body["employment_format"] == "individual"
    assert body["payout_details"] == "Карта 1234"
    assert (await partner.client.get(URL)).json()["display_name"] == "Новое Имя"


async def test_profile_update_rejects_an_invalid_inn(partner: Partner) -> None:
    response = await partner.post(
        URL,
        {
            "display_name": "Имя",
            "employment_format": "self_employed",
            "payout_details": "",
            "inn": "123",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "profile_invalid"


async def test_profile_update_requires_csrf(partner: Partner) -> None:
    response = await partner.client.post(
        URL, json={"display_name": "Имя", "employment_format": "individual"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


async def test_email_change_needs_the_current_password(partner: Partner) -> None:
    response = await partner.post(
        f"{URL}/email", {"new_email": "new@example.test", "current_password": "wrong"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_password"
    assert partner.codes == []


@pytest.mark.parametrize(
    ("new_email", "code"),
    [("not-an-email", "validation_error"), ("SAME", "same_email")],
)
async def test_email_change_rejects_bad_addresses(partner: Partner, new_email, code) -> None:
    new_email = partner.email.upper() if new_email == "SAME" else new_email

    response = await partner.post(
        f"{URL}/email", {"new_email": new_email, "current_password": PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


async def test_email_change_refuses_an_address_of_another_account(partner: Partner) -> None:
    other_id, other_email = await _create_agent()
    try:
        response = await partner.post(
            f"{URL}/email", {"new_email": other_email, "current_password": PASSWORD}
        )
    finally:
        await _delete_agents(other_id)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_taken"


async def test_email_change_with_the_right_code(partner: Partner) -> None:
    new_email = f"{uuid.uuid4()}@example.test"

    begin = await partner.post(
        f"{URL}/email", {"new_email": new_email, "current_password": PASSWORD}
    )
    assert begin.status_code == 200
    assert (await partner.client.get(URL)).json()["pending_email"] == new_email

    wrong = await partner.post(f"{URL}/email/confirm", {"code": "000000"})
    assert wrong.json()["error"]["code"] == "invalid_code"
    assert await partner.db_email() == partner.email

    done = await partner.post(f"{URL}/email/confirm", {"code": partner.codes[-1]})

    assert done.status_code == 200
    assert await partner.db_email() == new_email
    assert (await partner.client.get(URL)).json()["pending_email"] == ""


async def test_the_session_cookie_does_not_reveal_the_code(partner: Partner) -> None:
    await partner.post(
        f"{URL}/email",
        {"new_email": f"{uuid.uuid4()}@example.test", "current_password": PASSWORD},
    )

    payload = partner.client.cookies["session"].split(".")[0]
    decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode()

    assert partner.codes[-1] not in decoded
    assert "email_change" in json.loads(decoded)


async def test_code_is_locked_after_too_many_wrong_attempts(partner: Partner) -> None:
    await partner.post(
        f"{URL}/email",
        {"new_email": f"{uuid.uuid4()}@example.test", "current_password": PASSWORD},
    )

    for _ in range(5):
        wrong = await partner.post(f"{URL}/email/confirm", {"code": "000000"})
        assert wrong.json()["error"]["code"] == "invalid_code"
    locked = await partner.post(f"{URL}/email/confirm", {"code": partner.codes[-1]})

    assert locked.status_code == 400
    assert locked.json()["error"]["code"] == "code_expired"
    assert await partner.db_email() == partner.email


async def test_confirm_without_a_request_is_refused(partner: Partner) -> None:
    response = await partner.post(f"{URL}/email/confirm", {"code": "123456"})

    assert response.json()["error"]["code"] == "no_pending_change"


async def test_partner_still_onboarding_cannot_open_the_profile() -> None:
    login_rate_limiter.reset()
    agent_id, email = await _create_agent(with_format=False)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            me = (await client.get("/api/v1/site/me")).json()
            await client.post(
                "/api/v1/site/auth/login",
                json={"email": email, "password": PASSWORD},
                headers={CSRF_HEADER: me["csrf_token"]},
            )
            response = await client.get(URL)
    finally:
        await _delete_agents(agent_id)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "onboarding_required"


# --- ported from the old HTML profile tests ------------------------------------------------


def _update_body(**overrides) -> dict:
    body = {
        "display_name": "Профиль Тестов",
        "phone": "",
        "employment_format": "self_employed",
        "payout_details": "",
        "inn": "616706684677",
    }
    body.update(overrides)
    return body


@pytest.fixture
def notices(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    mocks = SimpleNamespace(admins=AsyncMock(), telegram=AsyncMock())
    monkeypatch.setattr(api_profile, "send_admin_profile_change_notice", mocks.admins)
    monkeypatch.setattr(api_profile, "send_payout_details_changed_notice", mocks.telegram)
    monkeypatch.setattr(api_profile.get_settings(), "admin_emails", "admin@example.com")
    return mocks


async def test_changing_payout_details_or_format_tells_the_admins_and_telegram(
    partner: Partner, notices
) -> None:
    response = await partner.post(
        URL,
        _update_body(employment_format="individual", payout_details="1234 5678 9012 3456", inn=""),
    )

    assert response.status_code == 200
    notices.admins.assert_awaited_once()
    admins, _who, changed = notices.admins.await_args.args
    assert admins == ["admin@example.com"]
    assert "реквизиты для выплат" in changed
    assert "формат сотрудничества" in changed
    notices.telegram.assert_awaited_once()


async def test_changing_only_the_name_notifies_nobody(partner: Partner, notices) -> None:
    response = await partner.post(URL, _update_body(display_name="Другое Имя"))

    assert response.status_code == 200
    notices.admins.assert_not_awaited()
    notices.telegram.assert_not_awaited()


async def test_a_phone_given_for_the_first_time_is_stored_normalized(partner: Partner) -> None:
    response = await partner.post(URL, _update_body(phone="+7 999 123-45-67"))

    assert response.status_code == 200
    assert response.json()["phone"] == "+79991234567"
    assert (await partner.db_agent()).phone_normalized == "+79991234567"


async def test_a_phone_used_by_another_account_is_refused(partner: Partner) -> None:
    async with session_factory() as session:
        other = Agent(email=f"{uuid.uuid4()}@example.test", phone_normalized="+79990001199")
        session.add(other)
        await session.commit()
        other_id = other.id
    try:
        response = await partner.post(URL, _update_body(phone="+7 999 000-11-99"))
    finally:
        await _delete_agents(other_id)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "profile_invalid"
    assert "уже используется другим аккаунтом" in response.json()["error"]["message"]
    assert (await partner.db_agent()).phone_normalized is None


async def test_an_email_code_that_has_expired_is_refused(
    partner: Partner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_profile, "EMAIL_CHANGE_CODE_TTL_SECONDS", -1)
    await partner.post(
        f"{URL}/email",
        {"new_email": f"{uuid.uuid4()}@example.test", "current_password": PASSWORD},
    )

    response = await partner.post(f"{URL}/email/confirm", {"code": partner.codes[-1]})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "code_expired"
    assert await partner.db_email() == partner.email
