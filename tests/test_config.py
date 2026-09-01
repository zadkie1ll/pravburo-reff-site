import pytest
from pydantic import ValidationError

from src.core.config import Settings

PRODUCTION_KWARGS = {
    "app_env": "production",
    "legacy_database_url": "postgresql+asyncpg://readonly:test@127.0.0.1:5432/legacy",
    "session_secret": "test-production-secret",
    "legacy_webhook_secret": "test-legacy-secret",
    "turnstile_secret_key": "test-turnstile",
    "smtp_host": "smtp.example.test",
    "internal_service_token": "test-internal-token",
}


def test_production_settings_are_valid_without_debug() -> None:
    settings = Settings(**PRODUCTION_KWARGS)
    assert settings.app_debug is False


def test_app_debug_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="APP_DEBUG must be false in production"):
        Settings(**{**PRODUCTION_KWARGS, "app_debug": True})
