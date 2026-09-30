from uuid import UUID

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
