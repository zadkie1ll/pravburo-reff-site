import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pravburo_ref_common.models import Agent, AgentRole

from src.main import app
from src.web.dependencies import optional_agent
from src.web.routes.spa import SPA_PATH_TEMPLATES, SPA_PATHS, build_spa_router

FAKE_AGENT = Agent(id=2, email="agent@example.com", role=AgentRole.AGENT)


def test_me_for_guest(client) -> None:
    response = client.get("/api/v1/site/me")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["role"] is None
    assert body["csrf_token"]


def test_me_for_agent(client) -> None:
    app.dependency_overrides[optional_agent] = lambda: FAKE_AGENT
    try:
        response = client.get("/api/v1/site/me")
    finally:
        app.dependency_overrides.pop(optional_agent, None)

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["role"] == "agent"


def test_faq_api_returns_items_and_links(client) -> None:
    response = client.get("/api/v1/site/faq")

    assert response.status_code == 200
    body = response.json()
    assert any(item["question"] == "Когда я получу деньги?" for item in body["items"])
    assert body["telegram_manager_url"]
    assert body["telegram_materials_url"]


def test_spa_router_absent_without_build(tmp_path) -> None:
    assert build_spa_router(tmp_path / "missing.html") is None


def test_spa_router_serves_index_for_migrated_paths(tmp_path) -> None:
    index = tmp_path / "index.html"
    index.write_text("<div id='root'></div>")
    spa_app = FastAPI()
    router = build_spa_router(index)
    assert router is not None
    spa_app.include_router(router)
    spa_client = TestClient(spa_app)

    concrete = [*SPA_PATHS, "/r/00000000-0000-4000-8000-000000000001"]
    for path in concrete:
        response = spa_client.get(path)
        assert response.status_code == 200
        assert "id='root'" in response.text
        assert response.headers["cache-control"] == "no-cache"
    assert spa_client.get("/never-a-spa-page").status_code == 404


def _normalized(path: str) -> str:
    """`/r/{referral_code:uuid}` (Starlette) and `/r/:referralCode` (React Router) compare equal."""
    return re.sub(r"\{[^}]+\}|:\w+", ":param", path)


def test_spa_paths_match_the_frontend_route_list() -> None:
    # The two lists must stay in sync: a path only in the backend serves a blank React
    # 404, a path only in the frontend never reaches React.
    source = (Path(__file__).parents[1] / "frontend" / "src" / "app" / "spaRoutes.ts").read_text()
    frontend_paths = {_normalized(path) for path in re.findall(r'"(/[^"]*)"', source)}

    assert frontend_paths == {_normalized(path) for path in (*SPA_PATHS, *SPA_PATH_TEMPLATES)}
