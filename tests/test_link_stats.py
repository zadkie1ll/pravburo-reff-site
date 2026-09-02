from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import ReferralLinkVisit

from src.main import app
from src.services.referrals import LinkStats

REFERRAL_CODE = UUID("00000000-0000-4000-8000-000000000098")


def test_conversion_rate_label_with_no_visits() -> None:
    assert LinkStats(visits=0, applications=0).conversion_rate_label == "—"


def test_conversion_rate_label_rounds_percentage() -> None:
    assert LinkStats(visits=3, applications=1).conversion_rate_label == "33%"


def test_conversion_rate_label_full_conversion() -> None:
    assert LinkStats(visits=5, applications=5).conversion_rate_label == "100%"


class _FakeVisitSession:
    def __init__(self, agent) -> None:
        self._agent = agent
        self.added: list[object] = []

    async def scalar(self, *args, **kwargs):
        return self._agent

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None


def test_visiting_referral_link_records_a_visit(monkeypatch) -> None:
    agent = SimpleNamespace(id=42, referral_code=REFERRAL_CODE)
    fake_session = _FakeVisitSession(agent)

    async def _get_session():
        yield fake_session

    app.dependency_overrides[get_session] = _get_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/r/{REFERRAL_CODE}")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert len(fake_session.added) == 1
    visit = fake_session.added[0]
    assert isinstance(visit, ReferralLinkVisit)
    assert visit.agent_id == 42
