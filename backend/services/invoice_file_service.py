"""Serve invoice source files without holding a DB connection during storage I/O."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass

from fastapi import HTTPException
from fastapi.responses import Response

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

logger = get_logger(__name__)


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


async def serve_invoice_file(invoice_id: int, user: UserContext) -> Response:
    """Return raw invoice bytes with inline Content-Disposition."""
    meta = await _load_invoice_file_meta(
        invoice_id,
        owner_user_id=invoice_owner_user_id(user),
    )

    data = await resolve_upload_bytes(meta.storage_path, meta.original_filename)
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
    return _binary_response(
        prepared,
        mime_type=meta.mime_type,
        filename=meta.original_filename,
    )
