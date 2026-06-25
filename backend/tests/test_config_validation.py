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


def test_legacy_jwt_expire_minutes_applied_when_access_not_set(monkeypatch):
    monkeypatch.delenv("JWT_ACCESS_EXPIRE_MINUTES", raising=False)
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "90")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    settings = Settings()
    assert settings.jwt_access_expire_minutes == 90


def test_jwt_access_expire_minutes_overrides_legacy(monkeypatch):
    monkeypatch.setenv("JWT_ACCESS_EXPIRE_MINUTES", "15")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "90")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("STORAGE_PATH", "/data")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    settings = Settings()
    assert settings.jwt_access_expire_minutes == 15


def test_local_startup_warnings(monkeypatch):
    monkeypatch.setattr(
        "config.settings.environment",
        "local",
        raising=False,
    )
    warnings = validate_settings_on_startup()
    assert isinstance(warnings, list)
