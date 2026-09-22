import re
from types import SimpleNamespace

from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import AgentRole

from src.main import app


class _NoOpSession:
    async def commit(self) -> None:
        return None


def _csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_admin_panel_lists_sections(client) -> None:
    response = client.get("/admin")

    assert response.status_code == 200
    assert "/admin/network/rates" in response.text
    assert "/admin/network/tree" in response.text
    # Разделы bounty (начисления и их суммы) - отдельный сервис, но ссылка на них
    # нужна прямо из главной админки, иначе адрес приходится помнить наизусть.
    assert "/admin/rewards" in response.text
    assert "/admin/reward-rates" in response.text


def test_admin_nav_shows_only_admin_panel_link(client) -> None:
    from src.core.totp import totp_now
    from src.services.protection import totp_rate_limiter
    from src.web.dependencies import require_pending_admin

    # Общий на все тесты лимитер: соседние файлы (например test_admin_2fa.py)
    # могли уже израсходовать попытки для этого клиента, сбрасываем перед своей.
    totp_rate_limiter.reset()

    admin = SimpleNamespace(
        id=99,
        email="admin@example.com",
        role=AgentRole.ADMIN,
        totp_secret=None,
        totp_enabled=False,
        is_active=True,
    )
    app.dependency_overrides[require_pending_admin] = lambda: admin

    async def _get_session():
        yield _NoOpSession()

    app.dependency_overrides[get_session] = _get_session
    try:
        csrf = _csrf_from(client.get("/admin/2fa/setup").text)
        code = totp_now(admin.totp_secret)
        login_response = client.post(
            "/admin/2fa/setup", data={"code": code, "csrf": csrf}, follow_redirects=False
        )
        assert login_response.status_code == 303

        response = client.get("/admin")
    finally:
        app.dependency_overrides.pop(require_pending_admin, None)
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert '<a href="/admin">Админ-панель</a>' in response.text
    assert '<a href="/profile">Профиль</a>' not in response.text
    assert '<a href="/payouts">Выплаты</a>' not in response.text
