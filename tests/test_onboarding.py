import re
from types import SimpleNamespace

import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole, EmploymentFormat

from src.main import app
from src.services.onboarding import needs_onboarding
from src.services.protection import login_rate_limiter
from src.web.dependencies import require_agent
from src.web.routes import auth as auth_route


@pytest.fixture(autouse=True)
def _reset_login_rate_limit() -> None:
    login_rate_limiter.reset()


def _fake_agent(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=3,
        email="fresh@example.com",
        role=AgentRole.AGENT,
        display_name="",
        phone_normalized=None,
        invited_by_agent_id=None,
        employment_format=None,
        payout_details=None,
        inn=None,
        is_active=True,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _NoOpSession:
    async def commit(self) -> None:
        return None

    async def scalar(self, *args, **kwargs):
        return None


def _login_as(agent) -> None:
    app.dependency_overrides[require_agent] = lambda: agent

    async def _get_session():
        yield _NoOpSession()

    app.dependency_overrides[get_session] = _get_session


def teardown_function() -> None:
    app.dependency_overrides.pop(require_agent, None)
    app.dependency_overrides.pop(get_session, None)


def _csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_needs_onboarding_true_for_fresh_agent() -> None:
    assert needs_onboarding(_fake_agent()) is True


def test_needs_onboarding_false_once_employment_format_set() -> None:
    agent = _fake_agent(employment_format=EmploymentFormat.SELF_EMPLOYED)
    assert needs_onboarding(agent) is False


def test_needs_onboarding_false_for_admin() -> None:
    agent = _fake_agent(role=AgentRole.ADMIN)
    assert needs_onboarding(agent) is False


def test_login_redirects_fresh_agent_to_onboarding(client, monkeypatch) -> None:
    agent = _fake_agent()

    async def _fake_authenticate(session, email, password):
        return agent

    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    csrf = _csrf_from(client.get("/login").text)

    response = client.post(
        "/login",
        data={"email": "fresh@example.com", "password": "correct", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding"


def test_login_redirects_configured_agent_to_cabinet(client, monkeypatch) -> None:
    agent = _fake_agent(employment_format=EmploymentFormat.INDIVIDUAL_ENTREPRENEUR)

    async def _fake_authenticate(session, email, password):
        return agent

    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    csrf = _csrf_from(client.get("/login").text)

    response = client.post(
        "/login",
        data={"email": "fresh@example.com", "password": "correct", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"


def test_onboarding_basic_requires_login(client) -> None:
    response = client.get("/onboarding", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_onboarding_basic_submit_saves_and_redirects_to_payout(client) -> None:
    agent = _fake_agent()
    _login_as(agent)
    csrf = _csrf_from(client.get("/onboarding").text)

    response = client.post(
        "/onboarding",
        data={
            "display_name": "Иван Иванов",
            "phone": "+7 999 123-45-67",
            "employment_format": EmploymentFormat.SELF_EMPLOYED.value,
            "csrf": csrf,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding/payout"
    assert agent.display_name == "Иван Иванов"
    assert agent.phone_normalized == "+79991234567"
    assert agent.employment_format == EmploymentFormat.SELF_EMPLOYED


def test_onboarding_basic_submit_requires_display_name(client) -> None:
    agent = _fake_agent()
    _login_as(agent)
    csrf = _csrf_from(client.get("/onboarding").text)

    response = client.post(
        "/onboarding",
        data={
            "display_name": "   ",
            "phone": "+7 999 123-45-67",
            "employment_format": EmploymentFormat.SELF_EMPLOYED.value,
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "Укажите ФИО" in response.text


def test_onboarding_payout_redirects_back_when_basic_step_incomplete(client) -> None:
    agent = _fake_agent()
    _login_as(agent)

    response = client.get("/onboarding/payout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/onboarding"


def test_onboarding_payout_submit_saves_and_redirects_to_cabinet(client) -> None:
    agent = _fake_agent(
        display_name="Иван Иванов", employment_format=EmploymentFormat.SELF_EMPLOYED
    )
    _login_as(agent)
    csrf = _csrf_from(client.get("/onboarding/payout").text)

    response = client.post(
        "/onboarding/payout",
        data={
            "payout_details": "1234 5678 9012 3456",
            "inn": "123456789012",
            "csrf": csrf,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
    assert agent.payout_details == "1234 5678 9012 3456"
    assert agent.inn == "123456789012"


def test_onboarding_payout_submit_rejects_invalid_inn(client) -> None:
    agent = _fake_agent(
        display_name="Иван Иванов", employment_format=EmploymentFormat.SELF_EMPLOYED
    )
    _login_as(agent)
    csrf = _csrf_from(client.get("/onboarding/payout").text)

    response = client.post(
        "/onboarding/payout",
        data={"payout_details": "1234", "inn": "abc", "csrf": csrf},
    )

    assert response.status_code == 400
    assert "Укажите корректный ИНН" in response.text


def test_onboarding_payout_submit_individual_does_not_require_inn(client) -> None:
    agent = _fake_agent(display_name="Иван Иванов", employment_format=EmploymentFormat.INDIVIDUAL)
    _login_as(agent)
    csrf = _csrf_from(client.get("/onboarding/payout").text)

    response = client.post(
        "/onboarding/payout",
        data={"payout_details": "", "inn": "", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert agent.inn is None
