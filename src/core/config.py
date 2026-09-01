from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "pravburo-reff-site"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    legacy_database_url: str
    legacy_db_schema: str = Field(default="public", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    public_base_url: str = "http://localhost:8000"
    session_secret: str = "development-only-change-me"
    legacy_webhook_secret: str = ""
    crm_service_url: str = "http://127.0.0.1:8042"
    internal_service_token: str = "development-internal-token"
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    submission_rate_limit: int = 10
    submission_rate_window_seconds: int = 60
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "no-reply@prav-buro.ru"
    smtp_use_tls: bool = True
    registration_code_ttl_seconds: int = 900
    password_reset_code_ttl_seconds: int = 900
    ui_preview_enabled: bool = False
    ui_preview_token: str = ""
    admin_emails: str = ""
    telegram_bot_username: str = ""
    telegram_bot_token: str = ""
    telegram_login_max_age_seconds: int = 86400
    yandex_client_id: str = ""
    yandex_client_secret: str = ""
    yandex_redirect_uri: str = "http://localhost:8000/auth/yandex/callback"

    @property
    def development_routes_enabled(self) -> bool:
        return self.app_env != "production"

    @property
    def admin_email_set(self) -> set[str]:
        return {email.strip().lower() for email in self.admin_emails.split(",") if email.strip()}

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ui_preview_enabled and not self.ui_preview_token:
            raise ValueError("UI_PREVIEW_TOKEN is required when UI preview is enabled")
        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in production")
            if self.session_secret == "development-only-change-me":
                raise ValueError("SESSION_SECRET must be configured in production")
            if self.internal_service_token == "development-internal-token":
                raise ValueError("INTERNAL_SERVICE_TOKEN must be configured in production")
            if not self.legacy_webhook_secret:
                raise ValueError("LEGACY_WEBHOOK_SECRET must be configured in production")
            if not self.turnstile_secret_key:
                raise ValueError("Turnstile must be configured in production")
            if not self.smtp_host:
                raise ValueError("SMTP must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
