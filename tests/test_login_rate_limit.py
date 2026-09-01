import re

import pytest

from src.services.protection import login_rate_limiter
from src.web.routes import auth as auth_route


async def _fake_authenticate(session, email, password):
    return None


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_route, "authenticate", _fake_authenticate)
    login_rate_limiter.reset()


def _csrf_token(client) -> str:
    page = client.get("/login")
    match = re.search(r'name="csrf" value="([^"]+)"', page.text)
    assert match is not None
    return match.group(1)


def test_login_is_rate_limited_after_repeated_attempts(client) -> None:
    csrf = _csrf_token(client)

    for _ in range(5):
        response = client.post(
            "/login",
            data={"email": "someone@example.com", "password": "wrong", "csrf": csrf},
        )
        assert response.status_code == 400

    blocked = client.post(
        "/login",
        data={"email": "someone@example.com", "password": "wrong", "csrf": csrf},
    )
    assert blocked.status_code == 429
    assert "Слишком много попыток" in blocked.text
