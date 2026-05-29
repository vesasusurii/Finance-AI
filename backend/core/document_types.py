"""Allowed document MIME types and validation helpers."""

import mimetypes
from pathlib import Path

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}

ALLOWED_DOCUMENT_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

OCR_READY_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


def resolve_document_mime(filename: str, content_type: str | None) -> str:
    mime = content_type or mimetypes.guess_type(filename)[0] or ""
    if mime == "image/jpg":
        return "image/jpeg"
    return mime


def validate_document_file(filename: str, content_type: str | None, size: int) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed: PDF, JPG, JPEG, PNG, DOCX."
        )
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError("File exceeds 20 MB limit.")
    mime = resolve_document_mime(filename, content_type)
    if mime not in ALLOWED_DOCUMENT_MIME:
        raise ValueError(
            "Unsupported file type. Allowed: PDF, JPG, JPEG, PNG, DOCX."
        )
    return mime


def is_ocr_ready(mime: str) -> bool:
    return mime in OCR_READY_MIME
