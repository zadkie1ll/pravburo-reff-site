import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat
from starlette.middleware.sessions import SessionMiddleware

from src.core.security import csrf_token
from src.main import app as site_app
from src.web.api_dependencies import CSRF_HEADER, ApiAdmin, ApiAgent, CsrfProtected
from src.web.api_errors import ApiError, api_error_handler
from src.web.dependencies import optional_agent

AGENT = Agent(
    id=2,
    email="agent@example.com",
    role=AgentRole.AGENT,
    is_active=True,
    employment_format=EmploymentFormat.SELF_EMPLOYED,
)
ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN, is_active=True)


def build_app(current: Agent | None) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.dependency_overrides[optional_agent] = lambda: current

    @app.get("/agent")
    async def agent_only(_: ApiAgent) -> dict:
        return {"ok": True}

    @app.get("/admin")
    async def admin_only(_: ApiAdmin) -> dict:
        return {"ok": True}

    @app.get("/token")
    async def token(request: Request) -> dict:
        return {"token": csrf_token(request.session)}

    @app.post("/write", dependencies=[CsrfProtected])
    async def write() -> dict:
        return {"ok": True}

    return app


def error_of(response) -> dict:
    return response.json()["error"]


def test_guest_gets_401_json_not_a_redirect() -> None:
    response = TestClient(build_app(None)).get("/agent", follow_redirects=False)

    assert response.status_code == 401
    assert error_of(response)["code"] == "unauthorized"


def test_inactive_agent_gets_401() -> None:
    blocked = Agent(id=3, email="b@example.com", role=AgentRole.AGENT, is_active=False)

    response = TestClient(build_app(blocked)).get("/agent")

    assert response.status_code == 401


def test_agent_without_employment_format_must_onboard() -> None:
    fresh = Agent(id=4, email="n@example.com", role=AgentRole.AGENT, is_active=True)

    response = TestClient(build_app(fresh)).get("/agent")

    assert response.status_code == 403
    assert error_of(response)["code"] == "onboarding_required"


def test_agent_passes_agent_dependency_but_not_admin() -> None:
    client = TestClient(build_app(AGENT))

    assert client.get("/agent").status_code == 200
    denied = client.get("/admin")
    assert denied.status_code == 403
    assert error_of(denied)["code"] == "forbidden"


def test_admin_passes_admin_dependency() -> None:
    assert TestClient(build_app(ADMIN)).get("/admin").status_code == 200


@pytest.mark.parametrize("header", [None, "wrong-token"])
def test_write_requires_matching_csrf_header(header) -> None:
    client = TestClient(build_app(AGENT))
    client.get("/token")  # starts the session so a token exists

    response = client.post("/write", headers={CSRF_HEADER: header} if header else {})

    assert response.status_code == 403
    assert error_of(response)["code"] == "csrf_failed"


def test_write_accepts_the_session_csrf_token() -> None:
    client = TestClient(build_app(AGENT))
    token = client.get("/token").json()["token"]

    assert client.post("/write", headers={CSRF_HEADER: token}).status_code == 200


def test_me_reports_onboarding_required(client) -> None:
    fresh = Agent(id=4, email="n@example.com", role=AgentRole.AGENT, is_active=True)
    site_app.dependency_overrides[optional_agent] = lambda: fresh
    try:
        body = client.get("/api/v1/site/me").json()
    finally:
        site_app.dependency_overrides.pop(optional_agent, None)

    assert body["authenticated"] is True
    assert body["onboarding_required"] is True
