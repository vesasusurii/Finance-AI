"""Tests for invoice file serving headers and PDF bytes."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from services.invoice_file_service import _normalize_serve_mime, serve_invoice_file


def test_normalize_serve_mime_prefers_pdf_for_pdf_extension() -> None:
    assert _normalize_serve_mime("application/octet-stream", "invoice.PDF") == "application/pdf"


@pytest.mark.asyncio
async def test_serve_invoice_file_returns_inline_pdf_response() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    pdf_bytes = b"%PDF-1.4 test %%EOF"

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
                        "file_size": len(pdf_bytes),
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
    assert response.headers["content-length"] == str(len(pdf_bytes))
    assert response.headers["content-disposition"].startswith(
        'inline; filename="20260629_Deloitte.pdf"'
    )


@pytest.mark.asyncio
async def test_serve_invoice_file_strips_leading_garbage_before_pdf() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    raw = b"\xef\xbb\xbf\n%PDF-1.4 body %%EOF"

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_meta",
            new=AsyncMock(
                return_value=type(
                    "Meta",
                    (),
                    {
                        "storage_path": "users/1/file.pdf",
                        "original_filename": "scan.pdf",
                        "mime_type": "application/pdf",
                        "file_size": len(raw),
                    },
                )()
            ),
        ),
        patch(
            "services.invoice_file_service.resolve_upload_bytes",
            new=AsyncMock(return_value=raw),
        ),
    ):
        response = await serve_invoice_file(12, user)

    assert response.body.startswith(b"%PDF")
    assert response.body.endswith(b"%%EOF")


@pytest.mark.asyncio
async def test_serve_invoice_file_rejects_html_payload() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_meta",
            new=AsyncMock(
                return_value=type(
                    "Meta",
                    (),
                    {
                        "storage_path": "users/1/file.pdf",
                        "original_filename": "scan.pdf",
                        "mime_type": "application/pdf",
                        "file_size": 20,
                    },
                )()
            ),
        ),
        patch(
            "services.invoice_file_service.resolve_upload_bytes",
            new=AsyncMock(return_value=b"<!DOCTYPE html><html></html>"),
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await serve_invoice_file(12, user)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_serve_invoice_file_preview_page_returns_jpeg() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    pdf_bytes = b"%PDF-1.4 test %%EOF"
    jpeg_bytes = b"\xff\xd8\xff fake jpeg"

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_bytes",
            new=AsyncMock(
                return_value=(
                    type(
                        "Meta",
                        (),
                        {
                            "storage_path": "users/1/file.pdf",
                            "original_filename": "20260629_Deloitte.pdf",
                            "mime_type": "application/pdf",
                            "file_size": len(pdf_bytes),
                        },
                    )(),
                    pdf_bytes,
                )
            ),
        ),
        patch(
            "services.invoice_file_service.pdf_page_count",
            return_value=1,
        ),
        patch(
            "services.invoice_file_service.render_pdf_page_jpeg",
            return_value=jpeg_bytes,
        ),
    ):
        from services.invoice_file_service import serve_invoice_file_preview_page

        response = await serve_invoice_file_preview_page(35, 1, user)

    assert response.status_code == 200
    assert response.body == jpeg_bytes
    assert response.media_type == "image/jpeg"


@pytest.mark.asyncio
async def test_serve_invoice_file_preview_returns_all_pages() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    pdf_bytes = b"%PDF-1.4 test %%EOF"
    render_result = type(
        "RenderResult",
        (),
        {
            "page_numbers": [1, 2],
            "images": [
                (b"\xff\xd8\xff page one", "image/jpeg"),
                (b"\xff\xd8\xff page two", "image/jpeg"),
            ],
        },
    )()

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_bytes",
            new=AsyncMock(
                return_value=(
                    type(
                        "Meta",
                        (),
                        {
                            "storage_path": "users/1/file.pdf",
                            "original_filename": "multi.pdf",
                            "mime_type": "application/pdf",
                            "file_size": len(pdf_bytes),
                        },
                    )(),
                    pdf_bytes,
                )
            ),
        ),
        patch(
            "services.invoice_file_service.render_pdf_pages",
            return_value=render_result,
        ) as mock_render,
    ):
        from services.invoice_file_service import serve_invoice_file_preview

        response = await serve_invoice_file_preview(35, user)

    payload = json.loads(response.body)
    assert response.status_code == 200
    assert response.media_type == "application/json"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert payload["pageCount"] == 2
    assert [page["pageNumber"] for page in payload["pages"]] == [1, 2]
    assert [page["contentType"] for page in payload["pages"]] == [
        "image/jpeg",
        "image/jpeg",
    ]
    mock_render.assert_called_once_with(
        pdf_bytes,
        parallel=True,
        max_dimension=2400,
        jpeg_quality=85,
    )


@pytest.mark.asyncio
async def test_serve_invoice_file_preview_rejects_non_pdf() -> None:
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_bytes",
            new=AsyncMock(
                return_value=(
                    type(
                        "Meta",
                        (),
                        {
                            "storage_path": "users/1/file.png",
                            "original_filename": "scan.png",
                            "mime_type": "image/png",
                            "file_size": 10,
                        },
                    )(),
                    b"not a pdf",
                )
            ),
        ),
        patch("services.invoice_file_service.render_pdf_pages") as mock_render,
    ):
        from services.invoice_file_service import serve_invoice_file_preview

        with pytest.raises(HTTPException) as exc:
            await serve_invoice_file_preview(35, user)

    assert exc.value.status_code == 404
    mock_render.assert_not_called()


@pytest.mark.asyncio
async def test_serve_invoice_file_retries_truncated_download() -> None:
    """Supabase's storage occasionally returns a short body with HTTP 200
    (seen only on the Azure-hosted backend). Serving must retry rather than
    hand the browser a truncated PDF."""
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    truncated = b"%PDF-1.4 partial, no trailer"
    full = b"%PDF-1.4 full body %%EOF"

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_meta",
            new=AsyncMock(
                return_value=type(
                    "Meta",
                    (),
                    {
                        "storage_path": "users/1/file.pdf",
                        "original_filename": "invoice.pdf",
                        "mime_type": "application/pdf",
                        "file_size": len(full),
                    },
                )()
            ),
        ),
        patch(
            "services.invoice_file_service.resolve_upload_bytes",
            new=AsyncMock(side_effect=[truncated, full]),
        ) as mock_resolve,
        patch("services.invoice_file_service.asyncio.sleep", new=AsyncMock()),
    ):
        response = await serve_invoice_file(35, user)

    assert mock_resolve.await_count == 2
    assert response.body == full


@pytest.mark.asyncio
async def test_serve_invoice_file_gives_up_after_max_retries() -> None:
    """When every attempt comes back truncated, stop retrying and fail loudly
    (502) rather than silently handing the browser a corrupted PDF."""
    user = type("User", (), {"user_id": 1, "email": "a@b.com", "role": "finance"})()
    truncated = b"%PDF-1.4 partial, no trailer"
    full_size = 9999

    with (
        patch(
            "services.invoice_file_service._load_invoice_file_meta",
            new=AsyncMock(
                return_value=type(
                    "Meta",
                    (),
                    {
                        "storage_path": "users/1/file.pdf",
                        "original_filename": "invoice.pdf",
                        "mime_type": "application/pdf",
                        "file_size": full_size,
                    },
                )()
            ),
        ),
        patch(
            "services.invoice_file_service.resolve_upload_bytes",
            new=AsyncMock(return_value=truncated),
        ) as mock_resolve,
        patch("services.invoice_file_service.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(HTTPException) as exc:
            await serve_invoice_file(35, user)

    assert mock_resolve.await_count == 3
    assert exc.value.status_code == 502


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
