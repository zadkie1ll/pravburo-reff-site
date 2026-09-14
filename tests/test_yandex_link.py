import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import itsdangerous
import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole

from src.main import app
from src.web.routes import auth as auth_route


def _fake_agent(agent_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(id=agent_id, role=AgentRole.AGENT)


class _AgentLookupSession:
    def __init__(self, agent):
        self._agent = agent

    async def get(self, model, pk):
        return self._agent if pk == self._agent.id else None


def _session_cookie(data: dict) -> str:
    settings = auth_route.get_settings()
    signer = itsdangerous.TimestampSigner(str(settings.session_secret))
    payload = base64.b64encode(json.dumps(data).encode())
    return signer.sign(payload).decode()


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_session, None)


def _enable_yandex(monkeypatch) -> None:
    settings = auth_route.get_settings()
    monkeypatch.setattr(settings, "yandex_client_id", "client-id")
    monkeypatch.setattr(settings, "yandex_client_secret", "client-secret")


def _login(client, agent) -> None:
    client.cookies.set("session", _session_cookie({"agent_id": agent.id}))

    async def _get_session():
        yield _AgentLookupSession(agent)

    app.dependency_overrides[get_session] = _get_session


def test_yandex_start_marks_link_mode_for_logged_in_agent(client, monkeypatch) -> None:
    _enable_yandex(monkeypatch)
    agent = _fake_agent()
    _login(client, agent)

    response = client.get("/auth/yandex/start", follow_redirects=False)

    assert response.status_code == 303
    assert "oauth.yandex.ru" in response.headers["location"]


def test_yandex_callback_links_identity_to_current_agent(client, monkeypatch) -> None:
    _enable_yandex(monkeypatch)
    agent = _fake_agent()
    _login(client, agent)

    start_response = client.get("/auth/yandex/start", follow_redirects=False)
    state = parse_qs(urlparse(start_response.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        auth_route, "fetch_yandex_profile", AsyncMock(return_value={"id": "yandex-42"})
    )
    link_mock = AsyncMock()
    monkeypatch.setattr(auth_route, "link_social_identity", link_mock)

    response = client.get(
        f"/auth/yandex/callback?code=any-code&state={state}", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/profile")
    assert "info=" in response.headers["location"]
    link_mock.assert_awaited_once()
    call_args = link_mock.await_args.args
    assert call_args[1] is agent
    assert call_args[2] == "yandex"
    assert call_args[3] == "yandex-42"


def test_yandex_callback_link_reports_conflict(client, monkeypatch) -> None:
    _enable_yandex(monkeypatch)
    agent = _fake_agent()
    _login(client, agent)

    start_response = client.get("/auth/yandex/start", follow_redirects=False)
    state = parse_qs(urlparse(start_response.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        auth_route, "fetch_yandex_profile", AsyncMock(return_value={"id": "yandex-42"})
    )
    monkeypatch.setattr(
        auth_route,
        "link_social_identity",
        AsyncMock(side_effect=ValueError("Этот аккаунт уже привязан к другому пользователю")),
    )

    response = client.get(
        f"/auth/yandex/callback?code=any-code&state={state}", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/profile")
    assert "error=" in response.headers["location"]


def test_yandex_start_without_login_does_not_mark_link_mode(client, monkeypatch) -> None:
    _enable_yandex(monkeypatch)

    async def _get_session():
        yield _AgentLookupSession(_fake_agent())

    app.dependency_overrides[get_session] = _get_session

    start_response = client.get("/auth/yandex/start", follow_redirects=False)
    state = parse_qs(urlparse(start_response.headers["location"]).query)["state"][0]

    monkeypatch.setattr(
        auth_route, "fetch_yandex_profile", AsyncMock(return_value={"id": "yandex-42"})
    )
    login_mock = AsyncMock(return_value=_fake_agent(99))
    monkeypatch.setattr(auth_route, "login_social_agent", login_mock)
    link_mock = AsyncMock()
    monkeypatch.setattr(auth_route, "link_social_identity", link_mock)

    response = client.get(
        f"/auth/yandex/callback?code=any-code&state={state}", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
    link_mock.assert_not_awaited()
    login_mock.assert_awaited_once()
