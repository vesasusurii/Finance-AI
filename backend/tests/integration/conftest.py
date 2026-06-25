"""Integration test fixtures — require Postgres (+ Redis for rate limits)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Env must be set before app/settings import.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://finance:test@localhost:5432/finance_ai_test",
    ),
)
os.environ.setdefault("JWT_SECRET", "integration-test-jwt-secret-32chars")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("STORAGE_PATH", "/tmp/finance-ai-integration-uploads")
os.environ.setdefault(
    "REDIS_URL",
    os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1"),
)
os.environ.setdefault("OPENAI_API_KEY", "sk-integration-placeholder")
os.environ.setdefault("EMAIL_INGEST_API_KEY", "test-ingest-key")
os.environ.setdefault("EMAIL_INGEST_USER_EMAIL", "finance@borek.com")

from datetime import datetime, timezone

from db.pool import async_session  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402
from services.jwt_service import create_access_token  # noqa: E402

FINANCE_EMAIL = "finance@borek.com"
FINANCE_PASSWORD = "changeme"


async def _ensure_finance_user() -> None:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == FINANCE_EMAIL)
        )
        user = result.scalar_one_or_none()
        password_hash = bcrypt.hashpw(
            FINANCE_PASSWORD.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        verified_at = datetime.now(timezone.utc)
        if user is None:
            session.add(
                User(
                    email=FINANCE_EMAIL,
                    password_hash=password_hash,
                    role="finance",
                    is_active=True,
                    email_verified_at=verified_at,
                    must_change_password=False,
                )
            )
        else:
            user.password_hash = password_hash
            user.is_active = True
            user.role = "finance"
            user.must_change_password = False
            user.email_verified_at = user.email_verified_at or verified_at
        await session.commit()


@pytest.fixture(autouse=True)
async def _integration_db_ready() -> AsyncIterator[None]:
    try:
        await _ensure_finance_user()
    except Exception as exc:
        pytest.skip(f"Integration DB not available: {exc}")
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
    ) as http_client:
        yield http_client


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == FINANCE_EMAIL)
        )
        user = result.scalar_one()
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=True,
        must_change_password=False,
    )
    client.cookies.set("access_token", token)
    return client
