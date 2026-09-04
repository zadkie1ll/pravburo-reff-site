from fastapi.testclient import TestClient
from pravburo_ref_common.models import Agent, AgentRole

from src.main import app
from src.web.dependencies import require_agent

FAKE_ADMIN_AGENT = Agent(id=2, email="admin2@example.com", role=AgentRole.ADMIN)


def test_cabinet_redirects_admin_to_admin_panel() -> None:
    app.dependency_overrides[require_agent] = lambda: FAKE_ADMIN_AGENT
    try:
        with TestClient(app) as client:
            response = client.get("/cabinet", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(require_agent, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
