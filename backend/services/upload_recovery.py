"""Startup recovery: re-enqueue invoice OCR for uploads stuck in processing/queued."""

from __future__ import annotations

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select

from config import settings
from core.debug_logger import get_logger
from core.queue import enqueue_process_invoice_upload
from core.redis_client import get_redis_connection
from db.pool import async_session
from models.invoice import Invoice
from models.uploaded_file import UploadedFile
from services.invoice_processing_service import schedule_invoice_ocr
from storage.factory import get_storage_backend

logger = get_logger(__name__)

MAX_RECOVERY_ATTEMPTS = 3
_RECOVERY_ATTEMPTS_KEY = "recovery:ocr:attempts:{upload_id}"
_RECOVERY_ATTEMPTS_TTL_SECONDS = 7 * 24 * 60 * 60


def _recovery_attempts(upload_id: int) -> int:
    raw = get_redis_connection().get(_RECOVERY_ATTEMPTS_KEY.format(upload_id=upload_id))
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _record_recovery_attempt(upload_id: int) -> int:
    redis = get_redis_connection()
    key = _RECOVERY_ATTEMPTS_KEY.format(upload_id=upload_id)
    attempts = int(redis.incr(key))
    if attempts == 1:
        redis.expire(key, _RECOVERY_ATTEMPTS_TTL_SECONDS)
    return attempts


def _clear_recovery_attempts(upload_id: int) -> None:
    get_redis_connection().delete(_RECOVERY_ATTEMPTS_KEY.format(upload_id=upload_id))


async def recover_stuck_invoice_uploads(
    openai_client: AsyncOpenAI | None,
    *,
    limit: int | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> int:
    """Re-enqueue OCR for invoice uploads stuck without an invoice row. Returns count enqueued."""
    if openai_client is None:
        return 0

    cap = limit if limit is not None else settings.max_startup_recovery_jobs
    if cap <= 0:
        return 0

    storage = get_storage_backend(http_client)
    recoverable: list[tuple[int, int]] = []

    async with async_session() as session:
        q = (
            select(
                UploadedFile.id,
                UploadedFile.uploaded_by,
                UploadedFile.storage_path,
                UploadedFile.processing_status,
            )
            .outerjoin(Invoice, Invoice.source_file_id == UploadedFile.id)
            .where(
                UploadedFile.file_kind == "invoice",
                UploadedFile.processing_status.in_(("processing", "queued")),
                Invoice.id.is_(None),
            )
            .order_by(UploadedFile.id.asc())
            .limit(cap)
        )
        rows = (await session.execute(q)).all()

        for upload_id, user_id, storage_path, status in rows:
            if not await storage.exists(storage_path):
                row = await session.get(UploadedFile, upload_id)
                if row is not None:
                    row.processing_status = "failed"
                    get_redis_connection().delete(f"lock:ocr:{upload_id}")
                    _clear_recovery_attempts(upload_id)
                    logger.warning(
                        "Upload %d has no storage file (%s); marked failed",
                        upload_id,
                        storage_path,
                    )
                continue

            attempts = _recovery_attempts(upload_id)
            if attempts >= MAX_RECOVERY_ATTEMPTS:
                row = await session.get(UploadedFile, upload_id)
                if row is not None:
                    row.processing_status = "failed"
                    get_redis_connection().delete(f"lock:ocr:{upload_id}")
                    _clear_recovery_attempts(upload_id)
                    logger.warning(
                        "Upload %d exceeded %d recovery attempts; marked failed",
                        upload_id,
                        MAX_RECOVERY_ATTEMPTS,
                    )
                continue

            row = await session.get(UploadedFile, upload_id)
            if row and row.processing_status == "processing":
                row.processing_status = "queued"
                get_redis_connection().delete(f"lock:ocr:{upload_id}")
            recoverable.append((upload_id, user_id))

        await session.commit()

    if not recoverable:
        return 0

    logger.info("Recovering %d stuck invoice upload(s) (cap=%d)", len(recoverable), cap)

    enqueued = 0
    for upload_id, user_id in recoverable:
        try:
            attempts = _record_recovery_attempt(upload_id)
            if settings.queue_mode == "inline":
                schedule_invoice_ocr(upload_id, user_id)
            else:
                enqueue_process_invoice_upload(upload_id, user_id)
            enqueued += 1
            logger.info(
                "Recovery enqueued upload_id=%d user_id=%d (attempt %d/%d)",
                upload_id,
                user_id,
                attempts,
                MAX_RECOVERY_ATTEMPTS,
            )
        except Exception as exc:
            logger.warning(
                "Could not enqueue recovery for upload_id=%d: %s",
                upload_id,
                exc,
            )

    if enqueued:
        logger.info("Recovery enqueued %d stuck invoice upload(s)", enqueued)
    return enqueued
