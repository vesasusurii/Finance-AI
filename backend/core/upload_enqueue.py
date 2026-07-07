"""Enqueue OCR after upload rows are committed — must not fail the upload API."""

from __future__ import annotations

from config import settings
from core.debug_logger import get_logger
from core.queue import enqueue_process_invoice_upload
from services.invoice_processing_service import schedule_invoice_ocr

logger = get_logger(__name__)


def safe_enqueue_invoice_ocr(
    upload_id: int,
    user_id: int,
    *,
    priority: str | None = None,
) -> None:
    if settings.queue_mode == "inline":
        schedule_invoice_ocr(upload_id, user_id)
        return

    try:
        enqueue_process_invoice_upload(
            upload_id,
            user_id,
            priority=priority,
        )
    except Exception as exc:
        logger.warning(
            "OCR enqueue failed upload_id=%d (row is saved; retry via status or recovery): %s",
            upload_id,
            exc,
        )
