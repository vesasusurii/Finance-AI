"""Serve invoice source files without holding a DB connection during storage I/O."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response

from core.debug_logger import get_logger
from core.invoice_access import invoice_owner_user_id
from db.pool import async_session
from repositories.invoice_repository import InvoiceRepository
from schemas.auth import UserContext
from utils.file_storage import resolve_upload_bytes, resolve_upload_path
from utils.pdf_bytes import (
    format_pdf_report,
    inspect_pdf_bytes,
    looks_like_html_or_json,
    normalize_pdf_bytes,
)
from utils.safe_filename import content_disposition_inline
from services.ocr.pdf_reader import (
    pdf_page_count,
    render_pdf_page_jpeg,
    render_pdf_pages,
)

logger = get_logger(__name__)

# Supabase's storage CDN occasionally ends a large download mid-stream without
# raising an HTTP error — seen intermittently on the Azure-hosted backend
# (never reproduced locally). The client gets a 200 with a shorter-than-expected
# body and no error, so pdf.js chokes on the missing trailer. Detect that by
# comparing against the recorded file size / PDF trailer and retry before
# giving up, instead of silently serving a truncated file.
_MAX_DOWNLOAD_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.4


@dataclass(frozen=True)
class _InvoiceFileMeta:
    storage_path: str
    original_filename: str
    mime_type: str
    file_size: int | None


def _normalize_serve_mime(mime: str | None, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if mime:
        return mime
    guessed = mimetypes.guess_type(filename)[0]
    return guessed or "application/octet-stream"


async def _load_invoice_file_meta(
    invoice_id: int,
    *,
    owner_user_id: int | None,
) -> _InvoiceFileMeta:
    async with async_session() as session:
        row = await InvoiceRepository(session).get_owned_row(
            invoice_id,
            owner_user_id=owner_user_id,
        )
        if not row:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )
        if not row.source_file_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "no_source_file",
                    "message": "No source file attached to this invoice.",
                },
            )

        upload = row.source_file
        if not upload:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "file_record_missing",
                    "message": "File record not found.",
                },
            )

        mime = _normalize_serve_mime(upload.mime_type, upload.original_filename)
        return _InvoiceFileMeta(
            storage_path=upload.storage_path,
            original_filename=upload.original_filename,
            mime_type=mime,
            file_size=upload.file_size,
        )


def _prepare_serve_bytes(
    invoice_id: int,
    meta: _InvoiceFileMeta,
    data: bytes,
) -> bytes:
    if not data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "file_empty",
                "message": "Invoice file is empty.",
            },
        )

    if looks_like_html_or_json(data):
        logger.error(
            "Invoice file %s storage=%s returned non-binary payload (HTML/JSON)",
            invoice_id,
            meta.storage_path,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "file_corrupt",
                "message": "Stored invoice file is not valid binary data.",
            },
        )

    report = inspect_pdf_bytes(data)
    logger.info(
        "Invoice file serve invoice_id=%s storage_path=%s expected_size=%s %s",
        invoice_id,
        meta.storage_path,
        meta.file_size,
        format_pdf_report(report),
    )

    if meta.file_size is not None and meta.file_size > 0 and len(data) != meta.file_size:
        logger.warning(
            "Invoice file size mismatch invoice_id=%s storage_path=%s "
            "db_size=%s served_size=%s",
            invoice_id,
            meta.storage_path,
            meta.file_size,
            len(data),
        )

    if meta.mime_type == "application/pdf":
        if not report.starts_with_pdf:
            logger.error(
                "Invoice PDF missing %%PDF header invoice_id=%s storage_path=%s",
                invoice_id,
                meta.storage_path,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "file_corrupt",
                    "message": "Stored file is not a valid PDF.",
                },
            )
        if report.leading_prefix_len > 0:
            logger.warning(
                "Invoice PDF has %d leading bytes before %%PDF invoice_id=%s",
                report.leading_prefix_len,
                invoice_id,
            )
            data = normalize_pdf_bytes(data)
        if report.likely_truncated:
            logger.warning(
                "Invoice PDF missing %%EOF marker invoice_id=%s storage_path=%s size=%s",
                invoice_id,
                meta.storage_path,
                len(data),
            )

    return data


def _binary_response(
    data: bytes,
    *,
    mime_type: str,
    filename: str,
) -> Response:
    headers = content_disposition_inline(filename)
    headers["Content-Length"] = str(len(data))
    return Response(content=data, media_type=mime_type, headers=headers)


def _download_looks_complete(meta: _InvoiceFileMeta, data: bytes) -> bool:
    if meta.file_size is not None and meta.file_size > 0 and len(data) != meta.file_size:
        return False
    if meta.mime_type == "application/pdf":
        report = inspect_pdf_bytes(data)
        if report.starts_with_pdf and report.likely_truncated:
            return False
    return True


async def _download_verified_bytes(
    invoice_id: int,
    meta: _InvoiceFileMeta,
) -> bytes | None:
    """Fetch storage bytes, retrying when the payload looks truncated.

    Returns None only when the object genuinely does not exist in storage
    (mirrors `resolve_upload_bytes`'s not-found signal for its local-disk
    fallback path).
    """
    last_data: bytes | None = None
    for attempt in range(1, _MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            data = await resolve_upload_bytes(meta.storage_path, meta.original_filename)
        except Exception as exc:  # noqa: BLE001 - retry any transient storage error
            logger.warning(
                "Invoice file download raised invoice_id=%s storage_path=%s "
                "attempt=%s/%s: %s",
                invoice_id,
                meta.storage_path,
                attempt,
                _MAX_DOWNLOAD_ATTEMPTS,
                exc,
            )
            if attempt < _MAX_DOWNLOAD_ATTEMPTS:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise
        if data is None:
            return None
        last_data = data

        if _download_looks_complete(meta, data):
            if attempt > 1:
                logger.info(
                    "Invoice file download recovered on retry invoice_id=%s "
                    "attempt=%s size=%s",
                    invoice_id,
                    attempt,
                    len(data),
                )
            return data

        logger.warning(
            "Invoice file download looks truncated invoice_id=%s storage_path=%s "
            "attempt=%s/%s expected_size=%s received_size=%s",
            invoice_id,
            meta.storage_path,
            attempt,
            _MAX_DOWNLOAD_ATTEMPTS,
            meta.file_size,
            len(data),
        )
        if attempt < _MAX_DOWNLOAD_ATTEMPTS:
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    logger.error(
        "Invoice file download still truncated after %d attempts invoice_id=%s "
        "storage_path=%s expected_size=%s received_size=%s — serving best-effort "
        "rather than failing the request outright",
        _MAX_DOWNLOAD_ATTEMPTS,
        invoice_id,
        meta.storage_path,
        meta.file_size,
        len(last_data) if last_data is not None else None,
    )
    return last_data


async def _load_invoice_file_bytes(
    invoice_id: int,
    user: UserContext,
) -> tuple[_InvoiceFileMeta, bytes]:
    """Load and validate invoice file bytes from storage."""
    meta = await _load_invoice_file_meta(
        invoice_id,
        owner_user_id=invoice_owner_user_id(user),
    )

    data = await _download_verified_bytes(invoice_id, meta)
    if data is None:
        file_path = resolve_upload_path(meta.storage_path, meta.original_filename)
        if file_path is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "file_missing",
                    "message": (
                        "Original file is not available in storage. "
                        "Re-upload the invoice to attach a new copy."
                    ),
                },
            )
        data = file_path.read_bytes()

    prepared = _prepare_serve_bytes(invoice_id, meta, data)
    return meta, prepared


async def serve_invoice_file(invoice_id: int, user: UserContext) -> Response:
    """Return raw invoice bytes with inline Content-Disposition."""
    meta, prepared = await _load_invoice_file_bytes(invoice_id, user)
    return _binary_response(
        prepared,
        mime_type=meta.mime_type,
        filename=meta.original_filename,
    )


async def serve_invoice_file_preview_page(
    invoice_id: int,
    page_number: int,
    user: UserContext,
) -> Response:
    """Render one PDF page to JPEG for preview when client-side viewers fail."""
    if page_number < 1:
        raise HTTPException(status_code=404, detail={"error": "page_not_found"})

    meta, prepared = await _load_invoice_file_bytes(invoice_id, user)
    if meta.mime_type != "application/pdf":
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_pdf",
                "message": "Preview pages are only available for PDF invoices.",
            },
        )

    try:
        total_pages = pdf_page_count(prepared)
        jpeg = render_pdf_page_jpeg(prepared, page_number)
    except IndexError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "page_not_found",
                "message": f"Page {page_number} does not exist in this PDF.",
            },
        ) from None
    except Exception as exc:
        logger.warning(
            "Invoice PDF preview render failed invoice_id=%s page=%s: %s",
            invoice_id,
            page_number,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "preview_render_failed",
                "message": (
                    "Could not render this PDF for preview. "
                    "The stored file may be corrupt - re-upload the invoice."
                ),
            },
        ) from exc

    headers = content_disposition_inline(
        f"{Path(meta.original_filename).stem}_p{page_number}.jpg"
    )
    headers["Content-Length"] = str(len(jpeg))
    headers["Cache-Control"] = "private, max-age=3600"
    headers["X-Pdf-Page-Count"] = str(total_pages)
    headers["X-Pdf-Page-Number"] = str(page_number)
    return Response(content=jpeg, media_type="image/jpeg", headers=headers)


async def serve_invoice_file_preview(
    invoice_id: int,
    user: UserContext,
) -> Response:
    """Render every PDF page to JPEG in one request for fast review previews."""
    meta, prepared = await _load_invoice_file_bytes(invoice_id, user)
    if meta.mime_type != "application/pdf":
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_pdf",
                "message": "Preview pages are only available for PDF invoices.",
            },
        )

    try:
        render_result = render_pdf_pages(
            prepared,
            parallel=True,
            max_dimension=2400,
            jpeg_quality=85,
        )
    except Exception as exc:
        logger.warning(
            "Invoice PDF batch preview render failed invoice_id=%s: %s",
            invoice_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "preview_render_failed",
                "message": (
                    "Could not render this PDF for preview. "
                    "The stored file may be corrupt - re-upload the invoice."
                ),
            },
        ) from exc

    pages = [
        {
            "pageNumber": page_number,
            "contentType": mime,
            "dataBase64": base64.b64encode(image).decode("ascii"),
        }
        for page_number, (image, mime) in zip(
            render_result.page_numbers,
            render_result.images,
            strict=True,
        )
    ]
    headers = {"Cache-Control": "private, max-age=3600"}
    return JSONResponse(
        content={"pageCount": len(pages), "pages": pages},
        headers=headers,
    )
