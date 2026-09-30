"""Where the Telegram and Yandex sign-in callbacks send the browser, on success and on failure.

A failure goes back to the React login page, which shows the message from ``?error=``.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole

from src.main import app
from src.web.routes import auth as auth_route


class _NoDb:
    async def get(self, model, pk):
        return None


@pytest.fixture(autouse=True)
def _no_database():
    async def _get_session():
        yield _NoDb()

    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.pop(get_session, None)


def _error_of(response) -> str:
    location = response.headers["location"]
    assert urlparse(location).path == "/login"
    return parse_qs(urlparse(location).query)["error"][0]


def _yandex_state(client, monkeypatch) -> str:
    settings = auth_route.get_settings()
    monkeypatch.setattr(settings, "yandex_client_id", "client-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "client-secret")
    start = client.get("/auth/yandex/start", follow_redirects=False)
    return parse_qs(urlparse(start.headers["location"]).query)["state"][0]


def test_telegram_login_that_cannot_be_verified_goes_back_to_login_with_a_message(client) -> None:
    response = client.get("/auth/telegram/callback?id=1&hash=bad", follow_redirects=False)

    assert response.status_code == 303
    assert _error_of(response) == "Не удалось проверить Telegram"


def test_a_verified_telegram_login_starts_a_session_and_opens_the_cabinet(
    client, monkeypatch
) -> None:
    settings = auth_route.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(auth_route, "verify_telegram_login", lambda *args: True)
    agent = SimpleNamespace(id=5, role=AgentRole.AGENT)
    login = AsyncMock(return_value=agent)
    monkeypatch.setattr(auth_route, "login_social_agent", login)

    response = client.get(
        "/auth/telegram/callback?id=777&first_name=Иван&last_name=Иванов&hash=ok",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
    assert login.await_args.args[1:4] == ("telegram", "777", "Иван Иванов")


def test_a_verified_telegram_admin_lands_in_the_admin_panel(client, monkeypatch) -> None:
    settings = auth_route.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(auth_route, "verify_telegram_login", lambda *args: True)
    admin = SimpleNamespace(id=1, role=AgentRole.ADMIN)
    monkeypatch.setattr(auth_route, "login_social_agent", AsyncMock(return_value=admin))

    response = client.get("/auth/telegram/callback?id=1&hash=ok", follow_redirects=False)

    assert response.headers["location"] == "/admin"


def test_yandex_failing_to_answer_goes_back_to_login_with_a_message(client, monkeypatch) -> None:
    state = _yandex_state(client, monkeypatch)
    monkeypatch.setattr(auth_route, "fetch_yandex_profile", AsyncMock(side_effect=RuntimeError))

    response = client.get(f"/auth/yandex/callback?code=x&state={state}", follow_redirects=False)

    assert response.status_code == 303
    assert _error_of(response) == "Не удалось войти через Яндекс"


def test_yandex_account_that_cannot_be_signed_in_goes_back_with_a_message(
    client, monkeypatch
) -> None:
    state = _yandex_state(client, monkeypatch)
    monkeypatch.setattr(auth_route, "fetch_yandex_profile", AsyncMock(return_value={"id": "y1"}))
    monkeypatch.setattr(auth_route, "login_social_agent", AsyncMock(side_effect=ValueError("x")))

    response = client.get(f"/auth/yandex/callback?code=x&state={state}", follow_redirects=False)

    assert _error_of(response) == "Не удалось войти через Яндекс"


def test_a_wrong_yandex_state_is_ignored_without_touching_yandex(client, monkeypatch) -> None:
    _yandex_state(client, monkeypatch)
    fetch = AsyncMock()
    monkeypatch.setattr(auth_route, "fetch_yandex_profile", fetch)

    response = client.get("/auth/yandex/callback?code=x&state=forged", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    fetch.assert_not_awaited()


def test_a_successful_yandex_login_opens_the_cabinet(client, monkeypatch) -> None:
    state = _yandex_state(client, monkeypatch)
    monkeypatch.setattr(auth_route, "fetch_yandex_profile", AsyncMock(return_value={"id": "y1"}))
    agent = SimpleNamespace(id=9, role=AgentRole.AGENT)
    monkeypatch.setattr(auth_route, "login_social_agent", AsyncMock(return_value=agent))

    response = client.get(f"/auth/yandex/callback?code=x&state={state}", follow_redirects=False)

    assert response.headers["location"] == "/cabinet"
