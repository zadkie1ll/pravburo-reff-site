import re
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole, EmploymentFormat

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
        is_active=True,
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _NoOpSession:
    async def commit(self) -> None:
        return None


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
