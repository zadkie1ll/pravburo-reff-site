import re
from types import SimpleNamespace

from src.web.routes import auth as auth_route


def _csrf_token(client) -> str:
    page = client.get("/register")
    match = re.search(r'name="csrf" value="([^"]+)"', page.text)
    assert match is not None
    return match.group(1)


def test_register_response_does_not_reveal_whether_email_exists(client, monkeypatch) -> None:
    csrf = _csrf_token(client)

    async def _fake_begin_registration_new(session, email, password):
        return SimpleNamespace(token="fake-token"), "123456"

    async def _fake_begin_registration_taken(session, email, password):
        return None

    monkeypatch.setattr(auth_route, "begin_registration", _fake_begin_registration_new)
    new_email_response = client.post(
        "/register",
        data={
            "email": "new@example.com",
            "password": "secret123",
            "password_repeat": "secret123",
            "csrf": csrf,
        },
    )

    csrf = _csrf_token(client)
    monkeypatch.setattr(auth_route, "begin_registration", _fake_begin_registration_taken)
    taken_email_response = client.post(
        "/register",
        data={
            "email": "taken@example.com",
            "password": "secret123",
            "password_repeat": "secret123",
            "csrf": csrf,
        },
    )

    assert new_email_response.status_code == taken_email_response.status_code == 200
    assert "Если почта свободна, код отправлен на неё" in new_email_response.text
    assert "Если почта свободна, код отправлен на неё" in taken_email_response.text
    assert "Такая почта уже используется" not in taken_email_response.text


def test_register_surfaces_smtp_error_for_new_email(client, monkeypatch) -> None:
    csrf = _csrf_token(client)

    async def _fake_begin_registration(session, email, password):
        return SimpleNamespace(token="fake-token"), "123456"

    async def _fake_send_code(email, code, purpose):
        raise RuntimeError("SMTP is not configured")

    monkeypatch.setattr(auth_route, "begin_registration", _fake_begin_registration)
    monkeypatch.setattr(auth_route, "send_code", _fake_send_code)

    response = client.post(
        "/register",
        data={
            "email": "new@example.com",
            "password": "secret123",
            "password_repeat": "secret123",
            "csrf": csrf,
        },
    )

    assert response.status_code == 400
    assert "SMTP is not configured" in response.text
