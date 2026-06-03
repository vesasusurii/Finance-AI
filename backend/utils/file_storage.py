import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile

from config import settings
from core.debug_logger import debug_trace, get_logger
from storage.factory import get_storage_backend

logger = get_logger(__name__)

_http_client: httpx.AsyncClient | None = None


def bind_http_client(client: httpx.AsyncClient) -> None:
    global _http_client
    _http_client = client


def _backend():
    return get_storage_backend(_http_client)


def build_user_storage_path(user_id: int, filename: str) -> str:
    safe_name = Path(filename or "upload").name
    return f"users/{user_id}/{uuid.uuid4()}_{safe_name}"


@debug_trace
async def save_bytes(
    content: bytes,
    *,
    user_id: int,
    filename: str,
    mime_type: str | None = None,
) -> tuple[str, int]:
    storage_path = build_user_storage_path(user_id, filename)
    await _backend().save(storage_path, content, content_type=mime_type)
    return storage_path, len(content)


@debug_trace
async def save_upload(file: UploadFile, user_id: int) -> tuple[str, int]:
    """Persist upload bytes under users/{user_id}/. Returns (storage_path, file_size)."""
    content = await file.read()
    filename = file.filename or "upload"
    mime = file.content_type
    await file.seek(0)
    return await save_bytes(
        content, user_id=user_id, filename=filename, mime_type=mime
    )


@debug_trace
async def read_bytes(storage_path: str) -> bytes:
    return await _backend().read(storage_path)


@debug_trace
async def delete_storage_object(storage_path: str) -> None:
    await _backend().delete(storage_path)


@debug_trace
def get_file_path(storage_path: str) -> Path:
    """Local filesystem path — only valid when STORAGE_BACKEND=local."""
    return Path(settings.storage_path) / storage_path


@debug_trace
async def resolve_upload_bytes(
    storage_path: str,
    original_filename: str | None = None,
) -> bytes | None:
    backend = _backend()
    try:
        # Read directly instead of HEAD + GET; on Supabase that saves one
        # network round-trip for every OCR fallback to storage.
        return await backend.read(storage_path)
    except FileNotFoundError:
        pass

    if not original_filename or settings.storage_backend != "local":
        return None

    invoices_dir = Path(settings.storage_path) / "invoices"
    if not invoices_dir.is_dir():
        return None

    suffix = f"_{original_filename}"
    for entry in invoices_dir.iterdir():
        if entry.is_file() and entry.name.endswith(suffix):
            logger.debug(
                "Resolved legacy local upload via filename fallback: %s",
                entry.name,
            )
            return entry.read_bytes()
    return None


@debug_trace
def resolve_upload_path(
    storage_path: str,
    original_filename: str | None = None,
) -> Path | None:
    """Return local path when file exists on disk (legacy local backend)."""
    if settings.storage_backend != "local":
        return None
    primary = get_file_path(storage_path)
    if primary.is_file():
        return primary

    if not original_filename:
        return None

    invoices_dir = Path(settings.storage_path) / "invoices"
    if not invoices_dir.is_dir():
        return None

    suffix = f"_{original_filename}"
    for entry in invoices_dir.iterdir():
        if entry.is_file() and entry.name.endswith(suffix):
            return entry
    return None
