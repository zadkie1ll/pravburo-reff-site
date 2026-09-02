import re
from types import SimpleNamespace

import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole, EmploymentFormat

from src.core.totp import totp_now
from src.main import app
from src.services.protection import login_rate_limiter, totp_rate_limiter
from src.web.dependencies import require_pending_admin
from src.web.routes import auth as auth_route


def _fake_admin(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=99,
        email="admin@example.com",
        role=AgentRole.ADMIN,
        totp_secret=None,
        totp_enabled=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _NoOpSession:
    async def commit(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    login_rate_limiter.reset()
    totp_rate_limiter.reset()
    yield
    app.dependency_overrides.pop(require_pending_admin, None)
    app.dependency_overrides.pop(get_session, None)


def _login_as_pending_admin(admin) -> None:
    app.dependency_overrides[require_pending_admin] = lambda: admin

    async def _get_session():
        yield _NoOpSession()

    app.dependency_overrides[get_session] = _get_session


def _csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def _login_csrf(client) -> str:
    return _csrf_from(client.get("/login").text)


def test_admin_login_without_2fa_redirects_to_setup(client, monkeypatch) -> None:
    admin = _fake_admin(totp_enabled=False)

    async def _fake_authenticate(session, email, password):
        return admin

    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    csrf = _login_csrf(client)

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "correct", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/2fa/setup"


def test_admin_login_with_2fa_enabled_redirects_to_verify(client, monkeypatch) -> None:
    admin = _fake_admin(totp_enabled=True, totp_secret="ABCDEFGHIJKLMNOP")

    async def _fake_authenticate(session, email, password):
        return admin

    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    csrf = _login_csrf(client)

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "correct", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/2fa/verify"


def test_regular_agent_login_skips_2fa(client, monkeypatch) -> None:
    agent = SimpleNamespace(
        id=5,
        role=AgentRole.AGENT,
        email="agent@example.com",
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )

    async def _fake_authenticate(session, email, password):
        return agent

    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    csrf = _login_csrf(client)

    response = client.post(
        "/login",
        data={"email": "agent@example.com", "password": "correct", "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"


def test_2fa_setup_requires_pending_admin_session(client) -> None:
    response = client.get("/admin/2fa/setup", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_2fa_setup_page_generates_secret_and_shows_qr(client) -> None:
    admin = _fake_admin()
    _login_as_pending_admin(admin)

    response = client.get("/admin/2fa/setup")

    assert response.status_code == 200
    assert admin.totp_secret is not None
    assert "/admin/2fa/qr.png" in response.text


def test_2fa_setup_confirm_with_correct_code_enables_and_logs_in(client) -> None:
    admin = _fake_admin()
    _login_as_pending_admin(admin)
    csrf = _csrf_from(client.get("/admin/2fa/setup").text)
    code = totp_now(admin.totp_secret)

    response = client.post(
        "/admin/2fa/setup",
        data={"code": code, "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"
    assert admin.totp_enabled is True


def test_2fa_setup_confirm_with_wrong_code_shows_error(client) -> None:
    admin = _fake_admin()
    _login_as_pending_admin(admin)
    csrf = _csrf_from(client.get("/admin/2fa/setup").text)

    response = client.post(
        "/admin/2fa/setup",
        data={"code": "000000", "csrf": csrf},
    )

    assert response.status_code == 400
    assert "Неверный код" in response.text
    assert admin.totp_enabled is False


def test_2fa_verify_redirects_to_setup_when_not_enabled(client) -> None:
    admin = _fake_admin(totp_enabled=False)
    _login_as_pending_admin(admin)

    response = client.get("/admin/2fa/verify", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/2fa/setup"


def test_2fa_verify_correct_code_logs_in(client) -> None:
    admin = _fake_admin(totp_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    _login_as_pending_admin(admin)
    csrf = _csrf_from(client.get("/admin/2fa/verify").text)
    code = totp_now(admin.totp_secret)

    response = client.post(
        "/admin/2fa/verify",
        data={"code": code, "csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/cabinet"


def test_2fa_verify_is_rate_limited_after_repeated_wrong_attempts(client) -> None:
    admin = _fake_admin(totp_enabled=True, totp_secret="JBSWY3DPEHPK3PXP")
    _login_as_pending_admin(admin)
    csrf = _csrf_from(client.get("/admin/2fa/verify").text)

    for _ in range(5):
        response = client.post(
            "/admin/2fa/verify",
            data={"code": "000000", "csrf": csrf},
        )
        assert response.status_code == 400

    blocked = client.post(
        "/admin/2fa/verify",
        data={"code": "000000", "csrf": csrf},
    )
    assert blocked.status_code == 429
