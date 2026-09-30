import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from pravburo_ref_common.database import engine, session_factory
from pravburo_ref_common.models import Agent, AgentCredential, AgentRole
from sqlalchemy import delete

from src.core.security import hash_password
from src.core.totp import generate_secret, totp_now
from src.main import app
from src.services.protection import login_rate_limiter, totp_rate_limiter
from src.web.api_dependencies import CSRF_HEADER

BASE = "/api/v1/site/admin/2fa"
PASSWORD = "admin-pass-1"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


@dataclass
class Pending:
    """An admin who has passed the password step (a real pending session cookie)."""

    client: AsyncClient
    admin_id: int

    async def post(self, path: str, body: dict):
        me = (await self.client.get("/api/v1/site/me")).json()
        return await self.client.post(path, json=body, headers={CSRF_HEADER: me["csrf_token"]})

    async def admin(self) -> Agent:
        async with session_factory() as session:
            return await session.get(Agent, self.admin_id)

    async def code(self) -> str:
        return totp_now((await self.admin()).totp_secret)

    async def me(self) -> dict:
        return (await self.client.get("/api/v1/site/me")).json()


async def _make_admin(*, totp_enabled: bool) -> tuple[int, str]:
    email = f"{uuid.uuid4()}@example.test"
    async with session_factory() as session:
        admin = Agent(
            email=email,
            role=AgentRole.ADMIN,
            totp_secret=generate_secret() if totp_enabled else None,
            totp_enabled=totp_enabled,
        )
        session.add(admin)
        await session.flush()
        session.add(AgentCredential(agent_id=admin.id, password_hash=hash_password(PASSWORD)))
        await session.commit()
        return admin.id, email


async def _delete_admin(admin_id: int) -> None:
    async with session_factory() as session:
        await session.execute(delete(AgentCredential).where(AgentCredential.agent_id == admin_id))
        await session.execute(delete(Agent).where(Agent.id == admin_id))
        await session.commit()


async def _password_step(client: AsyncClient, email: str) -> None:
    me = (await client.get("/api/v1/site/me")).json()
    response = await client.post(
        "/api/v1/site/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={CSRF_HEADER: me["csrf_token"]},
    )
    assert response.status_code == 200


@pytest.fixture(autouse=True)
def _reset_limiters() -> None:
    login_rate_limiter.reset()
    totp_rate_limiter.reset()


@pytest.fixture
async def new_admin() -> AsyncIterator[Pending]:
    """An admin who has never set up 2FA."""
    admin_id, email = await _make_admin(totp_enabled=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _password_step(client, email)
        yield Pending(client=client, admin_id=admin_id)
    await _delete_admin(admin_id)


@pytest.fixture
async def enrolled_admin() -> AsyncIterator[Pending]:
    """An admin with 2FA already on."""
    admin_id, email = await _make_admin(totp_enabled=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _password_step(client, email)
        yield Pending(client=client, admin_id=admin_id)
    await _delete_admin(admin_id)


async def test_nothing_works_without_the_password_step() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        me = (await client.get("/api/v1/site/me")).json()
        headers = {CSRF_HEADER: me["csrf_token"]}

        assert (await client.get(f"{BASE}/state")).status_code == 401
        assert (
            await client.post(f"{BASE}/setup", json={"code": "123456"}, headers=headers)
        ).status_code == 401
        assert (
            await client.post(f"{BASE}/verify", json={"code": "123456"}, headers=headers)
        ).status_code == 401


async def test_a_new_admin_is_sent_to_setup_and_gets_a_secret(new_admin: Pending) -> None:
    assert (await new_admin.admin()).totp_secret is None

    response = await new_admin.client.get(f"{BASE}/state")

    assert response.json() == {"step": "setup", "qr_url": "/admin/2fa/qr.png"}
    assert (await new_admin.admin()).totp_secret


async def test_an_enrolled_admin_is_sent_to_verify_without_a_qr(enrolled_admin: Pending) -> None:
    assert (await enrolled_admin.client.get(f"{BASE}/state")).json() == {
        "step": "verify",
        "qr_url": None,
    }


async def test_the_qr_image_is_served_to_the_pending_admin(new_admin: Pending) -> None:
    await new_admin.client.get(f"{BASE}/state")

    response = await new_admin.client.get("/admin/2fa/qr.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


async def test_setup_with_the_right_code_enables_2fa_and_logs_in(new_admin: Pending) -> None:
    await new_admin.client.get(f"{BASE}/state")

    response = await new_admin.post(f"{BASE}/setup", {"code": await new_admin.code()})

    assert response.status_code == 200
    assert response.json() == {"next": "/admin"}
    assert (await new_admin.admin()).totp_enabled is True
    me = await new_admin.me()
    assert (me["authenticated"], me["role"]) == (True, "admin")
    # The pending step is over.
    assert (await new_admin.client.get(f"{BASE}/state")).status_code == 401


async def test_setup_with_a_wrong_code_changes_nothing(new_admin: Pending) -> None:
    await new_admin.client.get(f"{BASE}/state")

    response = await new_admin.post(f"{BASE}/setup", {"code": "000000"})

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_code",
        "message": "Неверный код",
        "fields": {},
    }
    assert (await new_admin.admin()).totp_enabled is False
    assert (await new_admin.me())["authenticated"] is False


async def test_verify_with_the_right_code_logs_in(enrolled_admin: Pending) -> None:
    response = await enrolled_admin.post(f"{BASE}/verify", {"code": await enrolled_admin.code()})

    assert response.json() == {"next": "/admin"}
    me = await enrolled_admin.me()
    assert (me["authenticated"], me["role"]) == (True, "admin")


async def test_verify_with_a_wrong_or_malformed_code_is_refused(enrolled_admin: Pending) -> None:
    for code in ("000000", "abc", "", "1234567"):
        response = await enrolled_admin.post(f"{BASE}/verify", {"code": code})
        assert response.status_code == 400, code
        assert response.json()["error"]["code"] == "invalid_code"
    assert (await enrolled_admin.me())["authenticated"] is False


async def test_setup_is_refused_when_2fa_is_already_on(enrolled_admin: Pending) -> None:
    response = await enrolled_admin.post(f"{BASE}/setup", {"code": await enrolled_admin.code()})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_enabled"
    assert (await enrolled_admin.me())["authenticated"] is False


async def test_verify_is_refused_before_2fa_is_set_up(new_admin: Pending) -> None:
    await new_admin.client.get(f"{BASE}/state")

    response = await new_admin.post(f"{BASE}/verify", {"code": await new_admin.code()})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "setup_required"
    assert (await new_admin.me())["authenticated"] is False


async def test_too_many_wrong_codes_lock_even_the_right_one_out(enrolled_admin: Pending) -> None:
    limit = 5
    for _ in range(limit):
        assert (await enrolled_admin.post(f"{BASE}/verify", {"code": "000000"})).status_code == 400

    locked = await enrolled_admin.post(f"{BASE}/verify", {"code": await enrolled_admin.code()})

    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "rate_limited"
    assert (await enrolled_admin.me())["authenticated"] is False


async def test_the_limit_holds_across_setup_and_verify_for_the_same_admin(
    new_admin: Pending,
) -> None:
    await new_admin.client.get(f"{BASE}/state")
    for _ in range(5):
        await new_admin.post(f"{BASE}/setup", {"code": "000000"})

    locked = await new_admin.post(f"{BASE}/setup", {"code": await new_admin.code()})

    assert locked.status_code == 429
    assert (await new_admin.admin()).totp_enabled is False


async def test_looking_at_the_state_does_not_use_up_attempts(enrolled_admin: Pending) -> None:
    for _ in range(10):
        await enrolled_admin.client.get(f"{BASE}/state")

    response = await enrolled_admin.post(f"{BASE}/verify", {"code": await enrolled_admin.code()})

    assert response.status_code == 200


async def test_codes_require_csrf(enrolled_admin: Pending) -> None:
    response = await enrolled_admin.client.post(
        f"{BASE}/verify", json={"code": await enrolled_admin.code()}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert (await enrolled_admin.me())["authenticated"] is False
