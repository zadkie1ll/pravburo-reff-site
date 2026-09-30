from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pravburo_ref_common.database import get_session

from src.main import app
from src.services.protection import rate_limiter
from src.web.routes import api_referral

CODE = UUID("00000000-0000-4000-8000-000000000099")
URL = f"/api/v1/site/referral/{CODE}"
FORM = {"full_name": "Иван Иванов", "phone": "+79991234567"}


class FakeSession:
    """Stands in for the DB: finds one agent (or none) and records what is added."""

    def __init__(self, agent) -> None:
        self.agent = agent
        self.added: list = []
        self.commits = 0

    async def scalar(self, *args, **kwargs):
        return self.agent

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _agent(email: str | None = "agent@example.com") -> SimpleNamespace:
    return SimpleNamespace(id=7, email=email, referral_code=CODE)


@pytest.fixture(autouse=True)
def _isolate():
    rate_limiter.reset()
    yield
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def db():
    def use(agent) -> FakeSession:
        fake = FakeSession(agent)

        async def _get_session():
            yield fake

        app.dependency_overrides[get_session] = _get_session
        return fake

    return use


@pytest.fixture
def channels(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    mocks = SimpleNamespace(
        email=AsyncMock(),
        push=AsyncMock(),
        partner=AsyncMock(),
        chats=AsyncMock(),
        create=AsyncMock(return_value=(SimpleNamespace(full_name="Иван Иванов"), True)),
        captcha=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(api_referral, "send_referral_accepted_notice", mocks.email)
    monkeypatch.setattr(api_referral, "send_push_notice", mocks.push)
    monkeypatch.setattr(api_referral, "send_partner_notice", mocks.partner)
    monkeypatch.setattr(api_referral, "send_new_referral_notice", mocks.chats)
    monkeypatch.setattr(api_referral, "create_first_application", mocks.create)
    monkeypatch.setattr(api_referral, "verify_turnstile", mocks.captcha)
    return mocks


def test_opening_the_form_counts_a_visit_and_returns_the_site_key(client, db) -> None:
    fake = db(_agent())

    response = client.get(URL)

    assert response.status_code == 200
    assert set(response.json()) == {"turnstile_site_key"}
    assert len(fake.added) == 1 and fake.added[0].agent_id == 7
    assert fake.commits == 1


def test_unknown_link_is_a_404_and_counts_nothing(client, db) -> None:
    fake = db(None)

    get = client.get(URL)
    post = client.post(URL, json=FORM)

    assert get.status_code == post.status_code == 404
    assert get.json()["error"]["code"] == "not_found"
    assert fake.added == []


def test_malformed_code_is_a_validation_error(client) -> None:
    response = client.get("/api/v1/site/referral/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_a_new_application_is_created_and_the_partner_is_told_everywhere(
    client, db, channels
) -> None:
    db(_agent())

    response = client.post(URL, json={**FORM, "city": "Москва", "turnstile_token": "tok"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    application_input = channels.create.await_args.args[2]
    assert application_input.full_name == "Иван Иванов"
    assert application_input.city == "Москва"
    channels.captcha.assert_awaited_once()
    assert channels.captcha.await_args.args[0] == "tok"
    channels.email.assert_awaited_once_with("agent@example.com", "Иван Иванов")
    channels.push.assert_awaited_once()
    channels.partner.assert_awaited_once()
    channels.chats.assert_awaited_once()


def test_a_partner_without_email_still_gets_the_other_notices(client, db, channels) -> None:
    db(_agent(email=None))

    response = client.post(URL, json=FORM)

    assert response.status_code == 200
    channels.email.assert_not_awaited()
    channels.push.assert_awaited_once()


def test_a_duplicate_application_notifies_nobody(client, db, channels) -> None:
    db(_agent())
    channels.create.return_value = (SimpleNamespace(full_name="Иван Иванов"), False)

    response = client.post(URL, json=FORM)

    assert response.status_code == 200
    channels.email.assert_not_awaited()
    channels.push.assert_not_awaited()
    channels.chats.assert_not_awaited()


def test_one_failing_notice_does_not_lose_the_application_or_the_other_notices(
    client, db, channels
) -> None:
    db(_agent())
    channels.push.side_effect = RuntimeError("push service down")

    response = client.post(URL, json=FORM)

    assert response.status_code == 200
    channels.partner.assert_awaited_once()
    channels.chats.assert_awaited_once()


def test_bots_are_rejected_with_the_same_answer_as_the_rate_limit(client, db, channels) -> None:
    db(_agent())
    honeypot = client.post(URL, json={**FORM, "website": "http://spam.example"})
    channels.captcha.return_value = False
    captcha = client.post(URL, json=FORM)

    for response in (honeypot, captcha):
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "submission_rejected"
    channels.create.assert_not_awaited()


def test_submissions_are_rate_limited_per_ip(client, db, channels) -> None:
    db(_agent())
    limit = api_referral.get_settings().submission_rate_limit

    statuses = [client.post(URL, json=FORM).status_code for _ in range(limit + 1)]

    assert statuses[:limit] == [200] * limit
    assert statuses[-1] == 429


def test_a_too_short_name_is_refused_with_the_field(client, db, channels) -> None:
    db(_agent())

    response = client.post(URL, json={**FORM, "full_name": "Ив"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["message"] == "Укажите ФИО"
    assert "full_name" in error["fields"]
    channels.create.assert_not_awaited()


def test_the_services_refusal_reaches_the_client(client, db, channels) -> None:
    db(_agent())
    channels.create.side_effect = ValueError("Укажите корректный телефон")

    response = client.post(URL, json=FORM)

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "application_invalid",
        "message": "Укажите корректный телефон",
        "fields": {},
    }
