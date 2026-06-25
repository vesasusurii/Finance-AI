from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.integration.conftest import FINANCE_EMAIL, FINANCE_PASSWORD


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"email": FINANCE_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_and_me(client: AsyncClient) -> None:
    login = await client.post(
        "/api/auth/login",
        json={"email": FINANCE_EMAIL, "password": FINANCE_PASSWORD},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["email"] == FINANCE_EMAIL
    assert "user_id" in body

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == FINANCE_EMAIL


@pytest.mark.asyncio
async def test_forgot_password_generic_response(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/forgot-password",
        json={"email": FINANCE_EMAIL},
    )
    assert response.status_code == 200
    assert "account exists" in response.json()["message"].lower()
