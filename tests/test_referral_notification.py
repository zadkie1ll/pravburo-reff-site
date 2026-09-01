from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pravburo_ref_common.database import get_session

from src.main import app
from src.services.protection import rate_limiter
from src.web.routes import referrals as referrals_route

REFERRAL_CODE = UUID("00000000-0000-4000-8000-000000000099")


class _FakeAgentSession:
    def __init__(self, agent) -> None:
        self._agent = agent

    async def scalar(self, *args, **kwargs):
        return self._agent


def _fake_agent(email: str | None) -> SimpleNamespace:
    return SimpleNamespace(id=1, email=email, referral_code=REFERRAL_CODE)


def _override_session(agent) -> None:
    async def _get_session():
        yield _FakeAgentSession(agent)

    app.dependency_overrides[get_session] = _get_session


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    rate_limiter.reset()


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_session, None)


def _submit(client, **overrides):
    data = {
        "full_name": "Иван Иванов",
        "phone": "+79991234567",
    }
    data.update(overrides)
    return client.post(f"/r/{REFERRAL_CODE}", data=data, follow_redirects=False)


def test_new_referral_notifies_agent_with_email(client, monkeypatch) -> None:
    agent = _fake_agent(email="agent@example.com")
    _override_session(agent)
    application = SimpleNamespace(full_name="Иван Иванов")
    monkeypatch.setattr(
        referrals_route,
        "create_first_application",
        AsyncMock(return_value=(application, True)),
    )
    notify = AsyncMock()
    monkeypatch.setattr(referrals_route, "send_referral_accepted_notice", notify)

    response = _submit(client)

    assert response.status_code == 303
    notify.assert_awaited_once_with("agent@example.com", "Иван Иванов")


def test_duplicate_referral_does_not_notify(client, monkeypatch) -> None:
    agent = _fake_agent(email="agent@example.com")
    _override_session(agent)
    application = SimpleNamespace(full_name="Иван Иванов")
    monkeypatch.setattr(
        referrals_route,
        "create_first_application",
        AsyncMock(return_value=(application, False)),
    )
    notify = AsyncMock()
    monkeypatch.setattr(referrals_route, "send_referral_accepted_notice", notify)

    response = _submit(client)

    assert response.status_code == 303
    notify.assert_not_awaited()


def test_referral_without_agent_email_does_not_notify_or_crash(client, monkeypatch) -> None:
    agent = _fake_agent(email=None)
    _override_session(agent)
    application = SimpleNamespace(full_name="Иван Иванов")
    monkeypatch.setattr(
        referrals_route,
        "create_first_application",
        AsyncMock(return_value=(application, True)),
    )
    notify = AsyncMock()
    monkeypatch.setattr(referrals_route, "send_referral_accepted_notice", notify)

    response = _submit(client)

    assert response.status_code == 303
    notify.assert_not_awaited()


def test_notification_failure_does_not_break_submission(client, monkeypatch) -> None:
    agent = _fake_agent(email="agent@example.com")
    _override_session(agent)
    application = SimpleNamespace(full_name="Иван Иванов")
    monkeypatch.setattr(
        referrals_route,
        "create_first_application",
        AsyncMock(return_value=(application, True)),
    )
    monkeypatch.setattr(
        referrals_route,
        "send_referral_accepted_notice",
        AsyncMock(side_effect=RuntimeError("SMTP is not configured")),
    )

    response = _submit(client)

    assert response.status_code == 303
    assert response.headers["location"] == f"/r/{REFERRAL_CODE}/success"
