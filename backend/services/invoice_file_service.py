"""Serve invoice source files without holding a DB connection during storage I/O."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response

from core.invoice_access import invoice_owner_user_id
from db.pool import async_session
from repositories.invoice_repository import InvoiceRepository
from schemas.auth import UserContext
from utils.file_storage import resolve_upload_bytes, resolve_upload_path
from utils.safe_filename import content_disposition_inline


@dataclass(frozen=True)
class _InvoiceFileMeta:
    storage_path: str
    original_filename: str
    mime_type: str


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
        )


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
        return FileResponse(
            path=str(file_path),
            media_type=meta.mime_type,
            filename=meta.original_filename,
            headers=content_disposition_inline(meta.original_filename),
        )

    return Response(
        content=data,
        media_type=meta.mime_type,
        headers=content_disposition_inline(meta.original_filename),
    )
