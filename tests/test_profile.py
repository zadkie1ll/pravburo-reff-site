import re
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole, EmploymentFormat

from src.core.security import hash_password
from src.main import app
from src.web.dependencies import require_agent
from src.web.routes import profile as profile_route


def _fake_agent(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=7,
        email="agent@example.com",
        phone_normalized="+79991234567",
        display_name="Иван Иванов",
        role=AgentRole.AGENT,
        employment_format=None,
        payout_details=None,
        inn=None,
        invited_by_agent_id=None,
        is_active=True,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _NoOpSession:
    async def commit(self) -> None:
        return None

    async def scalar(self, *args, **kwargs) -> None:
        return None


class _ScalarNoneSession(_NoOpSession):
    pass


class _EmailChangeSession(_NoOpSession):
    def __init__(self, password_hash: str, email_taken: bool = False):
        self._password_hash = password_hash
        self._email_taken = email_taken

    async def get(self, model, pk):
        return SimpleNamespace(password_hash=self._password_hash)

    async def scalar(self, *args, **kwargs):
        return 1 if self._email_taken else None


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(require_agent, None)
    app.dependency_overrides.pop(get_session, None)


def _login_as(agent) -> None:
    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _NoOpSession()

    app.dependency_overrides[get_session] = _get_session


def _csrf_token(client) -> str:
    page = client.get("/profile")
    match = re.search(r'name="csrf" value="([^"]+)"', page.text)
    assert match is not None
    return match.group(1)


def test_profile_requires_login(client) -> None:
    response = client.get("/profile", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_profile_page_renders_current_data(client) -> None:
    _login_as(_fake_agent(display_name="Светлана Иванова"))

    response = client.get("/profile")

    assert response.status_code == 200
    assert "Светлана Иванова" in response.text
    assert "+79991234567" in response.text


def test_profile_update_rejects_invalid_inn(client) -> None:
    agent = _fake_agent()
    _login_as(agent)
    csrf = _csrf_token(client)

    response = client.post(
        "/profile",
        data={
            "display_name": "Иван Иванов",
            "employment_format": EmploymentFormat.SELF_EMPLOYED.value,
            "payout_details": "1234 5678 9012 3456",
            "inn": "123",
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "Укажите корректный ИНН" in response.text


def test_profile_update_saves_and_notifies_admins_on_payout_change(client, monkeypatch) -> None:
    agent = _fake_agent()
    _login_as(agent)
    csrf = _csrf_token(client)
    settings = profile_route.get_settings()
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    notify = AsyncMock()
    monkeypatch.setattr(profile_route, "send_admin_profile_change_notice", notify)

    response = client.post(
        "/profile",
        data={
            "display_name": "Иван Иванов",
            "employment_format": EmploymentFormat.SELF_EMPLOYED.value,
            "payout_details": "1234 5678 9012 3456",
            "inn": "123456789012",
            "csrf": csrf,
        },
    )

    assert response.status_code == 200
    assert "Профиль обновлён" in response.text
    assert agent.payout_details == "1234 5678 9012 3456"
    assert agent.employment_format == EmploymentFormat.SELF_EMPLOYED
    notify.assert_awaited_once()
    call_args = notify.await_args.args
    assert call_args[0] == ["admin@example.com"]
    assert "реквизиты для выплат" in call_args[2]
    assert "формат сотрудничества" in call_args[2]


def test_profile_update_sets_phone_when_first_provided(client) -> None:
    agent = _fake_agent(phone_normalized=None, employment_format=EmploymentFormat.INDIVIDUAL)
    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _ScalarNoneSession()

    app.dependency_overrides[get_session] = _get_session
    csrf = _csrf_token(client)

    response = client.post(
        "/profile",
        data={
            "display_name": "Иван Иванов",
            "employment_format": EmploymentFormat.INDIVIDUAL.value,
            "payout_details": "",
            "inn": "",
            "phone": "+7 999 123-45-67",
            "csrf": csrf,
        },
    )

    assert response.status_code == 200
    assert agent.phone_normalized == "+79991234567"


def test_profile_update_rejects_phone_used_by_another_account(client) -> None:
    agent = _fake_agent(phone_normalized=None, employment_format=EmploymentFormat.INDIVIDUAL)

    class _ConflictSession(_NoOpSession):
        async def scalar(self, *args, **kwargs) -> int:
            return 999

    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _ConflictSession()

    app.dependency_overrides[get_session] = _get_session
    csrf = _csrf_token(client)

    response = client.post(
        "/profile",
        data={
            "display_name": "Иван Иванов",
            "employment_format": EmploymentFormat.INDIVIDUAL.value,
            "payout_details": "",
            "inn": "",
            "phone": "+7 999 123-45-67",
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "уже используется другим аккаунтом" in response.text
    assert agent.phone_normalized is None


def test_profile_update_individual_does_not_require_inn(client) -> None:
    agent = _fake_agent(employment_format=EmploymentFormat.INDIVIDUAL)
    _login_as(agent)
    csrf = _csrf_token(client)

    response = client.post(
        "/profile",
        data={
            "display_name": "Иван Иванов",
            "employment_format": EmploymentFormat.INDIVIDUAL.value,
            "payout_details": "",
            "inn": "",
            "csrf": csrf,
        },
    )

    assert response.status_code == 200
    assert agent.inn is None


def _login_with_session(agent, session) -> None:
    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield session

    app.dependency_overrides[get_session] = _get_session


def test_profile_email_begin_rejects_wrong_password(client, monkeypatch) -> None:
    agent = _fake_agent()
    _login_with_session(agent, _EmailChangeSession(hash_password("correct-horse")))
    csrf = _csrf_token(client)
    send_code = AsyncMock()
    monkeypatch.setattr(profile_route, "send_code", send_code)

    response = client.post(
        "/profile/email",
        data={
            "new_email": "new@example.com",
            "current_password": "wrong-password",
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "Неверный пароль" in response.text
    send_code.assert_not_awaited()


def test_profile_email_begin_rejects_taken_email(client, monkeypatch) -> None:
    agent = _fake_agent()
    _login_with_session(
        agent, _EmailChangeSession(hash_password("correct-horse"), email_taken=True)
    )
    csrf = _csrf_token(client)
    send_code = AsyncMock()
    monkeypatch.setattr(profile_route, "send_code", send_code)

    response = client.post(
        "/profile/email",
        data={
            "new_email": "new@example.com",
            "current_password": "correct-horse",
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "уже используется другим аккаунтом" in response.text
    send_code.assert_not_awaited()


def test_profile_email_change_full_flow(client, monkeypatch) -> None:
    agent = _fake_agent()
    _login_with_session(agent, _EmailChangeSession(hash_password("correct-horse")))
    csrf = _csrf_token(client)
    send_code = AsyncMock()
    monkeypatch.setattr(profile_route, "send_code", send_code)

    begin_response = client.post(
        "/profile/email",
        data={
            "new_email": "new@example.com",
            "current_password": "correct-horse",
            "csrf": csrf,
        },
    )

    assert begin_response.status_code == 200
    assert "Код отправлен на новую почту" in begin_response.text
    send_code.assert_awaited_once()
    sent_email, sent_code, purpose = send_code.await_args.args
    assert sent_email == "new@example.com"
    assert purpose == "смена почты"

    confirm_csrf = _csrf_token(client)
    confirm_response = client.post(
        "/profile/email/confirm",
        data={"code": sent_code, "csrf": confirm_csrf},
    )

    assert confirm_response.status_code == 200
    assert "Почта изменена" in confirm_response.text
    assert agent.email == "new@example.com"


def test_profile_email_confirm_rejects_wrong_code(client, monkeypatch) -> None:
    agent = _fake_agent()
    _login_with_session(agent, _EmailChangeSession(hash_password("correct-horse")))
    csrf = _csrf_token(client)
    monkeypatch.setattr(profile_route, "send_code", AsyncMock())

    client.post(
        "/profile/email",
        data={
            "new_email": "new@example.com",
            "current_password": "correct-horse",
            "csrf": csrf,
        },
    )
    confirm_csrf = _csrf_token(client)

    response = client.post(
        "/profile/email/confirm",
        data={"code": "000000", "csrf": confirm_csrf},
    )

    assert response.status_code == 400
    assert "Неверный код" in response.text
    assert agent.email == "agent@example.com"


def test_profile_email_confirm_rejects_expired_code(client, monkeypatch) -> None:
    agent = _fake_agent()
    session_obj = _EmailChangeSession(hash_password("correct-horse"))
    _login_with_session(agent, session_obj)
    csrf = _csrf_token(client)
    send_code = AsyncMock()
    monkeypatch.setattr(profile_route, "send_code", send_code)
    monkeypatch.setattr(profile_route, "EMAIL_CHANGE_CODE_TTL_SECONDS", -1)

    client.post(
        "/profile/email",
        data={
            "new_email": "new@example.com",
            "current_password": "correct-horse",
            "csrf": csrf,
        },
    )
    sent_code = send_code.await_args.args[1]

    confirm_csrf = _csrf_token(client)
    response = client.post(
        "/profile/email/confirm",
        data={"code": sent_code, "csrf": confirm_csrf},
    )

    assert response.status_code == 400
    assert "Код истёк" in response.text
    assert agent.email == "agent@example.com"
