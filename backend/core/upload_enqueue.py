"""Enqueue OCR after upload rows are committed — must not fail the upload API."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from config import settings
from core.debug_logger import get_logger
from core.ocr_progress import update_ocr_progress
from core.queue import enqueue_process_invoice_upload
from core.redis_client import get_redis_connection
from core.upload_handoff import store_upload_bytes
from redis.exceptions import RedisError
from services.invoice_processing_service import schedule_invoice_ocr

logger = get_logger(__name__)

_STALE_QUEUE_SECONDS = 45
_REENQUEUE_DEBOUNCE_SECONDS = 120


def safe_enqueue_invoice_ocr(
    upload_id: int,
    user_id: int,
    *,
    priority: str | None = None,
    content: bytes | None = None,
) -> None:
    update_ocr_progress(
        upload_id,
        stage="queued",
        stage_label="Queued",
        upload_status="queued",
        queued_at=time.time(),
        model=settings.openai_model,
    )
    if settings.queue_mode == "inline":
        schedule_invoice_ocr(upload_id, user_id, content=content)
        return

    try:
        store_upload_bytes(upload_id, content)
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


def maybe_reenqueue_stale_invoice_ocr(
    upload_id: int,
    user_id: int,
    *,
    processing_status: str,
    uploaded_at: datetime,
) -> None:
    """Re-enqueue uploads left in queued when the initial enqueue or worker was down."""
    if settings.queue_mode == "inline":
        return
    if processing_status != "queued":
        return

    uploaded = uploaded_at
    if uploaded.tzinfo is None:
        uploaded = uploaded.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - uploaded).total_seconds()
    if age_seconds < _STALE_QUEUE_SECONDS:
        return

    try:
        redis = get_redis_connection()
        debounce_key = f"reenqueue:ocr:{upload_id}"
        if not redis.set(debounce_key, b"1", nx=True, ex=_REENQUEUE_DEBOUNCE_SECONDS):
            return
    except RedisError as exc:
        logger.debug("OCR stale re-enqueue debounce skipped upload_id=%d: %s", upload_id, exc)
        return

    logger.info(
        "Re-enqueueing stale queued upload_id=%d (age=%.0fs)",
        upload_id,
        age_seconds,
    )
    safe_enqueue_invoice_ocr(upload_id, user_id, priority="high")
