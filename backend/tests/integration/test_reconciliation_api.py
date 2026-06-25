from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_reconciliation_run_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/reconciliation/run", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reconciliation_run_empty(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/reconciliation/run", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] >= 0
    assert "run_at" in body


@pytest.mark.asyncio
async def test_reconciliation_results_list(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/reconciliation/results")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert isinstance(body["items"], list)
