"""Tests for invoice file serving headers and PDF bytes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from services.invoice_file_service import _normalize_serve_mime, serve_invoice_file


def test_normalize_serve_mime_prefers_pdf_for_pdf_extension() -> None:
    assert _normalize_serve_mime("application/octet-stream", "invoice.PDF") == "application/pdf"


@pytest.mark.asyncio
async def test_serve_invoice_file_returns_inline_pdf_response() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    pdf_bytes = b"%PDF-1.4 test"

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_meta",
            new=AsyncMock(
                return_value=type(
                    "Meta",
                    (),
                    {
                        "storage_path": "users/1/file.pdf",
                        "original_filename": "20260629_Deloitte.pdf",
                        "mime_type": "application/pdf",
                    },
                )()
            ),
        ),
        patch(
            "services.invoice_file_service.resolve_upload_bytes",
            new=AsyncMock(return_value=pdf_bytes),
        ),
    ):
        response = await serve_invoice_file(35, user)

    assert response.status_code == 200
    assert response.body == pdf_bytes
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"].startswith(
        'inline; filename="20260629_Deloitte.pdf"'
    )


@pytest.mark.asyncio
async def test_serve_invoice_file_not_found() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()

    with patch(
        "services.invoice_file_service._load_invoice_file_meta",
        new=AsyncMock(side_effect=HTTPException(status_code=404, detail="missing")),
    ):
        with pytest.raises(HTTPException) as exc:
            await serve_invoice_file(999, user)
    assert exc.value.status_code == 404
