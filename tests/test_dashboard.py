from src.core.config import Settings, get_settings
from src.main import app


def test_dashboard_renders_existing_client(client) -> None:
    response = client.get("/dev/clients/123")

    assert response.status_code == 200
    assert "Иванов Иван Иванович" in response.text
    assert "ivan@example.com" in response.text


def test_dashboard_returns_html_404(client) -> None:
    response = client.get("/dev/clients/404404")

    assert response.status_code == 404
    assert "Клиент не найден" in response.text


def test_agent_auth_pages_and_cabinet_redirect(client) -> None:
    assert client.get("/login").status_code == 200
    assert client.get("/register").status_code == 200
    response = client.get("/cabinet", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_development_dashboard_is_hidden_in_production(client) -> None:
    production_settings = Settings(
        app_env="production",
        legacy_database_url="postgresql+asyncpg://readonly:test@127.0.0.1:5432/legacy",
        session_secret="test-production-secret",
        legacy_webhook_secret="test-legacy-secret",
        turnstile_secret_key="test-turnstile",
        smtp_host="smtp.example.test",
        internal_service_token="test-internal-token",
    )
    app.dependency_overrides[get_settings] = lambda: production_settings

    response = client.get("/dev/clients/123")

    assert response.status_code == 404
    assert "Клиент не найден" in response.text
