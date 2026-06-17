import pytest
from pydantic import ValidationError

from config import Settings, validate_settings_on_startup


def test_production_rejects_weak_jwt(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    with pytest.raises(ValidationError):
        Settings()


def test_normalizes_render_postgres_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("JWT_SECRET", "local-dev-jwt-secret-minimum-32-chars")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@dpg.example.com/finance_ai",
    )
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    settings = Settings()

    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_local_startup_warnings(monkeypatch):
    monkeypatch.setattr(
        "config.settings.environment",
        "local",
        raising=False,
    )
    warnings = validate_settings_on_startup()
    assert isinstance(warnings, list)
