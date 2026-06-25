from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.integration

# Minimal valid PDF header (single empty page is not required for upload acceptance).
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<<>>endobj\n"
    b"xref\n0 1\n0000000000 65535 f \n"
    b"trailer<<>>\n"
    b"%%EOF\n"
)


@pytest.mark.asyncio
async def test_invoice_upload_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/invoices/upload",
        files={"files": ("sample.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invoice_upload_accepted(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/invoices/upload",
        files={"files": ("sample.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["uploaded"] >= 1
    assert len(body["items"]) >= 1
    item = body["items"][0]
    assert item["upload_id"] > 0
    assert item["processing_status"] in (
        "saved",
        "queued",
        "processing",
        "completed",
        "failed",
    )
