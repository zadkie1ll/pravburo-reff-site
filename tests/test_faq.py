from pravburo_ref_common.models import Agent, AgentRole

from src.main import app
from src.web.dependencies import require_agent

FAKE_AGENT = Agent(id=2, email="agent@example.com", role=AgentRole.AGENT)


def test_faq_requires_login(client) -> None:
    response = client.get("/faq", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_faq_renders_for_logged_in_agent(client) -> None:
    app.dependency_overrides[require_agent] = lambda: FAKE_AGENT
    try:
        response = client.get("/faq")
    finally:
        app.dependency_overrides.pop(require_agent, None)

    assert response.status_code == 200
    assert "Когда я получу деньги?" in response.text
    assert "Как зафиксировать клиента за собой?" in response.text
    assert "Написать менеджеру" in response.text
    assert "Открыть материалы" in response.text
