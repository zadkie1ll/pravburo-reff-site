import pytest
from pravburo_ref_common.models import Agent, AgentRole

from src.core.config import get_settings
from src.services.protection import login_rate_limiter
from src.web.api_dependencies import CSRF_HEADER
from src.web.routes import api_auth

AGENT = Agent(id=2, email="agent@example.com", role=AgentRole.AGENT, is_active=True)
ADMIN = Agent(
    id=1, email="admin@example.com", role=AgentRole.ADMIN, is_active=True, totp_enabled=False
)
LOGIN_URL = "/api/v1/site/auth/login"
CREDENTIALS = {"email": "someone@example.com", "password": "secret1"}


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    login_rate_limiter.reset()


def _authenticates_as(monkeypatch: pytest.MonkeyPatch, agent: Agent | None) -> None:
    async def fake(session, email, password):
        return agent

    monkeypatch.setattr(api_auth, "authenticate", fake)


def _csrf(client) -> dict[str, str]:
    return {CSRF_HEADER: client.get("/api/v1/site/me").json()["csrf_token"]}


def test_config_exposes_login_options(client) -> None:
    body = client.get("/api/v1/site/auth/config").json()

    assert set(body) == {"telegram_bot_username", "telegram_auth_url", "yandex_enabled"}
    assert body["telegram_auth_url"].endswith("/auth/telegram/callback")


def test_login_requires_csrf_header(client, monkeypatch) -> None:
    _authenticates_as(monkeypatch, AGENT)

    response = client.post(LOGIN_URL, json=CREDENTIALS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_wrong_credentials(client, monkeypatch) -> None:
    _authenticates_as(monkeypatch, None)

    response = client.post(LOGIN_URL, json=CREDENTIALS, headers=_csrf(client))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_blocked_account_gets_the_reason(client, monkeypatch) -> None:
    _authenticates_as(
        monkeypatch,
        Agent(
            id=3,
            email="b@example.com",
            role=AgentRole.AGENT,
            is_active=False,
            blocked_reason="Нарушение правил",
        ),
    )

    response = client.post(LOGIN_URL, json=CREDENTIALS, headers=_csrf(client))

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "account_blocked"
    assert "Нарушение правил" in error["message"]


def test_agent_login_goes_to_cabinet_and_starts_a_session(client, monkeypatch) -> None:
    _authenticates_as(monkeypatch, AGENT)

    response = client.post(LOGIN_URL, json=CREDENTIALS, headers=_csrf(client))

    assert response.status_code == 200
    assert response.json() == {"next": "/cabinet"}
    assert "session" in response.cookies or client.cookies.get("session")


@pytest.mark.parametrize(
    ("totp_enabled", "expected"),
    [(False, "/admin/2fa/setup"), (True, "/admin/2fa/verify")],
)
def test_admin_login_goes_through_2fa(client, monkeypatch, totp_enabled, expected) -> None:
    ADMIN.totp_enabled = totp_enabled
    _authenticates_as(monkeypatch, ADMIN)

    response = client.post(LOGIN_URL, json=CREDENTIALS, headers=_csrf(client))

    assert response.json() == {"next": expected}


def test_login_is_rate_limited(client, monkeypatch) -> None:
    _authenticates_as(monkeypatch, None)
    headers = _csrf(client)

    for _ in range(5):
        assert client.post(LOGIN_URL, json=CREDENTIALS, headers=headers).status_code == 400
    blocked = client.post(LOGIN_URL, json=CREDENTIALS, headers=headers)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


# --- registration and password reset ---------------------------------------------------


class FakePending:
    def __init__(self, token: str = "pending-token", email: str = "new@example.com") -> None:
        self.token = token
        self.email = email


class Recorder:
    """Stands in for the DB/e-mail/Telegram side effects the endpoints trigger."""

    def __init__(self) -> None:
        self.codes: list[tuple[str, str, str]] = []
        self.notices: list[Agent] = []
        self.tokens: list[str] = []


@pytest.fixture
def side_effects(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    recorder = Recorder()

    async def send_code(email, code, purpose):
        recorder.codes.append((email, code, purpose))

    async def notice(agent):
        recorder.notices.append(agent)

    monkeypatch.setattr(api_auth, "send_code", send_code)
    monkeypatch.setattr(api_auth, "send_new_partner_notice", notice)
    return recorder


def _post(client, path: str, body: dict):
    return client.post(f"/api/v1/site/auth/{path}", json=body, headers=_csrf(client))


REGISTER = {"email": "New@Example.com", "password": "secret1", "password_repeat": "secret1"}


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"email": "not-an-email"}, "email"),
        ({"password": "abc", "password_repeat": "abc"}, "password"),
        ({"password_repeat": "different"}, "password_repeat"),
    ],
)
def test_register_validates_input(client, side_effects, patch, field) -> None:
    response = _post(client, "register", {**REGISTER, **patch})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["fields"]
    assert side_effects.codes == []


def test_register_sends_a_code_and_remembers_the_token(client, side_effects, monkeypatch) -> None:
    async def begin(session, email, password):
        assert email == "new@example.com"
        return FakePending(), "123456"

    async def confirm(session, token, code):
        side_effects.tokens.append(token)
        return AGENT

    monkeypatch.setattr(api_auth, "begin_registration", begin)
    monkeypatch.setattr(api_auth, "confirm_registration", confirm)

    response = _post(client, "register", REGISTER)

    assert response.status_code == 200
    assert side_effects.codes == [("new@example.com", "123456", "регистрация")]
    _post(client, "register/confirm", {"code": "123456"})
    assert side_effects.tokens == ["pending-token"]


def test_register_answers_the_same_for_a_taken_address(client, side_effects, monkeypatch) -> None:
    async def taken(session, email, password):
        return None

    async def fresh(session, email, password):
        return FakePending(), "123456"

    monkeypatch.setattr(api_auth, "begin_registration", taken)
    taken_response = _post(client, "register", REGISTER)
    monkeypatch.setattr(api_auth, "begin_registration", fresh)
    fresh_response = _post(client, "register", REGISTER)

    assert taken_response.status_code == fresh_response.status_code == 200
    assert taken_response.json() == fresh_response.json()
    assert len(side_effects.codes) == 1  # only the free address got a code


def test_register_reports_a_delivery_failure(client, side_effects, monkeypatch) -> None:
    async def begin(session, email, password):
        raise RuntimeError("Почта не настроена")

    monkeypatch.setattr(api_auth, "begin_registration", begin)

    response = _post(client, "register", REGISTER)

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "registration_failed",
        "message": "Почта не настроена",
        "fields": {},
    }


def test_register_confirm_logs_a_new_agent_in_and_notifies(
    client, side_effects, monkeypatch
) -> None:
    async def confirm(session, token, code):
        return AGENT

    monkeypatch.setattr(api_auth, "confirm_registration", confirm)

    response = _post(client, "register/confirm", {"code": "123456"})

    assert response.json() == {"next": "/cabinet"}
    assert side_effects.notices == [AGENT]


def test_register_confirm_rejects_a_bad_code(client, side_effects, monkeypatch) -> None:
    async def confirm(session, token, code):
        raise ValueError("Неверный или просроченный код")

    monkeypatch.setattr(api_auth, "confirm_registration", confirm)

    response = _post(client, "register/confirm", {"code": "000000"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_code"


def test_registered_admin_goes_through_2fa_without_a_partner_notice(
    client, side_effects, monkeypatch
) -> None:
    ADMIN.totp_enabled = False

    async def confirm(session, token, code):
        return ADMIN

    monkeypatch.setattr(api_auth, "confirm_registration", confirm)

    response = _post(client, "register/confirm", {"code": "123456"})

    assert response.json() == {"next": "/admin/2fa/setup"}
    assert side_effects.notices == []


def test_password_reset_only_mails_known_accounts(client, side_effects, monkeypatch) -> None:
    async def known(session, email):
        return FakePending(email="agent@example.com"), "654321"

    async def unknown(session, email):
        return None

    monkeypatch.setattr(api_auth, "begin_password_reset", unknown)
    unknown_response = _post(client, "password-reset", {"email": "x@example.com"})
    monkeypatch.setattr(api_auth, "begin_password_reset", known)
    known_response = _post(client, "password-reset", {"email": "agent@example.com"})

    assert unknown_response.json() == known_response.json()
    assert side_effects.codes == [("agent@example.com", "654321", "восстановление пароля")]


def test_password_reset_confirm_validates_and_uses_the_session_token(
    client, side_effects, monkeypatch
) -> None:
    calls: list[tuple[str, str, str]] = []

    async def begin(session, email):
        return FakePending(token="reset-token", email="agent@example.com"), "654321"

    async def confirm(session, token, code, password):
        calls.append((token, code, password))
        return AGENT

    monkeypatch.setattr(api_auth, "begin_password_reset", begin)
    monkeypatch.setattr(api_auth, "confirm_password_reset", confirm)
    _post(client, "password-reset", {"email": "agent@example.com"})

    mismatch = _post(
        client,
        "password-reset/confirm",
        {"code": "654321", "password": "newpass1", "password_repeat": "other"},
    )
    ok = _post(
        client,
        "password-reset/confirm",
        {"code": "654321", "password": "newpass1", "password_repeat": "newpass1"},
    )

    assert mismatch.status_code == 400
    assert "password_repeat" in mismatch.json()["error"]["fields"]
    assert ok.json() == {"next": "/cabinet"}
    assert calls == [("reset-token", "654321", "newpass1")]


def test_password_reset_confirm_rejects_a_bad_code(client, side_effects, monkeypatch) -> None:
    async def confirm(session, token, code, password):
        raise ValueError("Неверный или просроченный код")

    monkeypatch.setattr(api_auth, "confirm_password_reset", confirm)

    response = _post(
        client,
        "password-reset/confirm",
        {"code": "000000", "password": "newpass1", "password_repeat": "newpass1"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_code"


def test_malformed_api_payload_uses_the_uniform_error_format(client) -> None:
    response = client.post("/api/v1/site/auth/login", json={}, headers=_csrf(client))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert set(error["fields"]) == {"email", "password"}


def test_routes_outside_the_api_keep_the_default_validation_error(client, monkeypatch) -> None:
    # Only /api/... uses the uniform error format; e.g. the internal service API keeps FastAPI's.
    monkeypatch.setattr(get_settings(), "internal_service_token", "test-token")

    response = client.post(
        "/internal/applications/1/stage", json={}, headers={"X-Internal-Token": "test-token"}
    )

    assert response.status_code == 422
    assert "detail" in response.json()
