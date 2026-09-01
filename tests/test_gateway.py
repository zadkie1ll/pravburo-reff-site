from datetime import UTC, datetime
from types import SimpleNamespace

from src.integrations.legacy_lk.gateway import LegacyClientGateway


class FakeResult:
    def __init__(self, row) -> None:
        self._row = row

    def one_or_none(self):
        return self._row


class FakeSession:
    def __init__(self, row) -> None:
        self.row = row
        self.executed = False

    async def execute(self, statement):
        self.executed = True
        assert statement.is_select
        return FakeResult(self.row)


async def test_gateway_reads_and_maps_legacy_client() -> None:
    joined = datetime(2024, 8, 1, tzinfo=UTC)
    client = SimpleNamespace(
        id=15,
        name="Петр",
        surname="Петров",
        middlename=None,
        stage_id=2,
        bitrix_id="321",
    )
    session = FakeSession((client, "petr@example.com", joined))

    record = await LegacyClientGateway(session).get_by_id(15)  # type: ignore[arg-type]

    assert session.executed is True
    assert record is not None
    assert record.full_name == "Петров Петр"
    assert record.registered_at == joined


async def test_gateway_returns_none_for_unknown_client() -> None:
    session = FakeSession(None)

    record = await LegacyClientGateway(session).get_by_id(999)  # type: ignore[arg-type]

    assert record is None
