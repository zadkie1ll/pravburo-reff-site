from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pravburo_ref_common.database import engine
from pravburo_ref_common.models import AgentRole, EmploymentFormat

from src.web.dependencies import require_agent


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    yield
    await engine.dispose()


class _FakeSession:
    def __init__(self, agent) -> None:
        self._agent = agent

    async def get(self, model, agent_id):
        return self._agent


def _request(path: str):
    return SimpleNamespace(session={"agent_id": 1}, url=SimpleNamespace(path=path))


def _agent(**overrides) -> SimpleNamespace:
    defaults = dict(role=AgentRole.AGENT, employment_format=None, is_active=True)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize("path", ["/cabinet", "/payouts", "/profile", "/cabinet/visits"])
async def test_agent_without_employment_format_is_sent_to_onboarding(path) -> None:
    with pytest.raises(HTTPException) as exc:
        await require_agent(_request(path), _FakeSession(_agent()))

    assert exc.value.status_code == 303
    assert exc.value.headers["Location"] == "/onboarding"


async def test_onboarding_page_itself_is_reachable_without_format() -> None:
    agent = _agent()
    assert await require_agent(_request("/onboarding"), _FakeSession(agent)) is agent


async def test_agent_with_format_and_admins_use_the_cabinet_freely() -> None:
    with_format = _agent(employment_format=EmploymentFormat.SELF_EMPLOYED)
    assert await require_agent(_request("/cabinet"), _FakeSession(with_format)) is with_format

    admin = _agent(role=AgentRole.ADMIN)
    assert await require_agent(_request("/admin"), _FakeSession(admin)) is admin
