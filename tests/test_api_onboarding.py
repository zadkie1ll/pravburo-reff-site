import pytest
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import Agent, AgentRole, EmploymentFormat

from src.main import app
from src.web.api_dependencies import CSRF_HEADER
from src.web.dependencies import optional_agent
from src.web.routes import api_onboarding

URL = "/api/v1/site/onboarding"


class FakeDbSession:
    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.commits = 0

    async def get(self, model, key):
        return self.agent

    async def commit(self) -> None:
        self.commits += 1


def _fresh_agent() -> Agent:
    return Agent(id=5, email="new@example.com", role=AgentRole.AGENT, is_active=True)


@pytest.fixture
def as_agent(client):
    """Log the test client in as the given agent and give back the fake DB session."""

    def login(agent: Agent) -> FakeDbSession:
        db = FakeDbSession(agent)
        app.dependency_overrides[optional_agent] = lambda: agent
        app.dependency_overrides[get_session] = lambda: db
        return db

    yield login
    app.dependency_overrides.pop(optional_agent, None)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def notices(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    sent: list[list[str]] = []

    async def notify(admin_emails, who, changes):
        sent.append(changes)

    monkeypatch.setattr(api_onboarding, "send_admin_profile_change_notice", notify)
    monkeypatch.setattr(
        api_onboarding.get_settings(), "admin_emails", "admin@example.com", raising=False
    )
    return sent


def _csrf(client) -> dict[str, str]:
    return {CSRF_HEADER: client.get("/api/v1/site/me").json()["csrf_token"]}


def test_options_require_a_session(client) -> None:
    response = client.get(URL)

    assert response.status_code == 401


def test_options_list_the_three_formats_for_a_partner_still_onboarding(client, as_agent) -> None:
    as_agent(_fresh_agent())

    response = client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert [option["value"] for option in body["options"]] == [
        "self_employed",
        "individual_entrepreneur",
        "individual",
    ]
    assert body["telegram_manager_url"]
    titles = [option["title"] for option in body["options"]]
    assert titles == ["Самозанятый", "ИП", "Физическое лицо"]
    texts = " ".join(option["text"] for option in body["options"])
    assert "налог 4%" in texts and "43%" in texts


def test_choosing_a_format_saves_it_and_notifies_admins(client, as_agent, notices) -> None:
    agent = _fresh_agent()
    db = as_agent(agent)

    response = client.post(URL, json={"employment_format": "self_employed"}, headers=_csrf(client))

    assert response.json() == {"next": "/cabinet"}
    assert agent.employment_format == EmploymentFormat.SELF_EMPLOYED
    assert db.commits == 1
    assert notices == [["формат сотрудничества"]]


def test_choosing_again_does_not_change_the_saved_format(client, as_agent, notices) -> None:
    agent = _fresh_agent()
    agent.employment_format = EmploymentFormat.INDIVIDUAL
    db = as_agent(agent)

    response = client.post(URL, json={"employment_format": "self_employed"}, headers=_csrf(client))

    assert response.json() == {"next": "/cabinet"}
    assert agent.employment_format == EmploymentFormat.INDIVIDUAL
    assert db.commits == 0
    assert notices == []


def test_unknown_format_is_rejected(client, as_agent) -> None:
    as_agent(_fresh_agent())

    response = client.post(URL, json={"employment_format": "astronaut"}, headers=_csrf(client))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_choosing_a_format_requires_csrf(client, as_agent) -> None:
    as_agent(_fresh_agent())

    response = client.post(URL, json={"employment_format": "self_employed"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_logout_ends_the_session(client) -> None:
    response = client.post("/api/v1/site/auth/logout", headers=_csrf(client))

    assert response.json() == {"next": "/login"}
    assert response.status_code == 200
