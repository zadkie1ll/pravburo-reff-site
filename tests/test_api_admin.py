from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat

from src.main import app
from src.web.dependencies import optional_agent

URL = "/api/v1/site/admin"


def _get(client, agent):
    app.dependency_overrides[optional_agent] = lambda: agent
    try:
        return client.get(URL)
    finally:
        app.dependency_overrides.pop(optional_agent, None)


def test_guest_is_refused(client) -> None:
    assert _get(client, None).status_code == 401


def test_partner_is_refused(client) -> None:
    partner = Agent(
        id=2,
        email="p@example.test",
        role=AgentRole.AGENT,
        is_active=True,
        employment_format=EmploymentFormat.SELF_EMPLOYED,
    )

    response = _get(client, partner)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_admin_gets_the_sections_including_the_bounty_ones(client) -> None:
    admin = Agent(id=1, email="a@example.test", role=AgentRole.ADMIN, is_active=True)

    response = _get(client, admin)

    assert response.status_code == 200
    sections = response.json()["sections"]
    urls = [section["url"] for section in sections]
    assert "/admin/partners" in urls
    assert "/admin/network/tree" in urls
    # Live in the bounty service, but must be reachable from the panel.
    assert "/admin/rewards" in urls
    assert "/admin/reward-rates" in urls
    assert all(section["title"] and section["description"] for section in sections)
