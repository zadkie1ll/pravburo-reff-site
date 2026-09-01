from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.api.dependencies import get_legacy_client_gateway
from src.api.v1.schemas import LegacyClientResponse
from src.integrations.legacy_lk.gateway import LegacyClientRecord
from src.main import app


def test_get_client_requires_admin(fake_gateway) -> None:
    app.dependency_overrides[get_legacy_client_gateway] = lambda: fake_gateway
    try:
        with TestClient(app) as anonymous_client:
            response = anonymous_client.get("/api/v1/legacy-clients/123", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_get_existing_client(client) -> None:
    response = client.get("/api/v1/legacy-clients/123")

    assert response.status_code == 200
    assert response.json() == {
        "id": 123,
        "full_name": "Иванов Иван Иванович",
        "email": "ivan@example.com",
        "registered_at": "2025-01-02T10:30:00Z",
        "stage_id": 4,
    }


def test_missing_client_returns_404(client) -> None:
    response = client.get("/api/v1/legacy-clients/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_legacy_record_is_explicitly_transformed() -> None:
    record = LegacyClientRecord(
        id=7,
        name="Анна",
        surname="Смирнова",
        middlename=None,
        email=None,
        registered_at=datetime(2025, 5, 4, tzinfo=UTC),
        stage_id=None,
    )

    response = LegacyClientResponse.from_record(record)

    assert response.model_dump() == {
        "id": 7,
        "full_name": "Смирнова Анна",
        "email": None,
        "registered_at": datetime(2025, 5, 4, tzinfo=UTC),
        "stage_id": None,
    }
