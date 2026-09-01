import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@127.0.0.1:5432/test",
)
os.environ.setdefault(
    "LEGACY_DATABASE_URL",
    "postgresql+asyncpg://test:test@127.0.0.1:5432/legacy",
)
os.environ.setdefault("APP_ENV", "test")

from pravburo_ref_common.models import Agent, AgentRole  # noqa: E402

from src.api.dependencies import get_legacy_client_gateway  # noqa: E402
from src.integrations.legacy_lk.gateway import LegacyClientRecord  # noqa: E402
from src.main import app  # noqa: E402
from src.web.dependencies import require_admin  # noqa: E402

FAKE_ADMIN = Agent(id=1, email="admin@example.com", role=AgentRole.ADMIN)


class FakeLegacyClientGateway:
    def __init__(self) -> None:
        self.clients = {
            123: LegacyClientRecord(
                id=123,
                name="Иван",
                surname="Иванов",
                middlename="Иванович",
                email="ivan@example.com",
                registered_at=datetime(2025, 1, 2, 10, 30, tzinfo=UTC),
                stage_id=4,
            )
        }

    async def get_by_id(self, client_id: int) -> LegacyClientRecord | None:
        return self.clients.get(client_id)


@pytest.fixture
def fake_gateway() -> FakeLegacyClientGateway:
    return FakeLegacyClientGateway()


@pytest.fixture
def client(fake_gateway: FakeLegacyClientGateway) -> TestClient:
    app.dependency_overrides[get_legacy_client_gateway] = lambda: fake_gateway
    app.dependency_overrides[require_admin] = lambda: FAKE_ADMIN
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
