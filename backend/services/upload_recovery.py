"""Startup recovery: re-enqueue invoice OCR for uploads stuck in processing/queued."""

from __future__ import annotations

from openai import AsyncOpenAI
from sqlalchemy import select

from config import settings
from core.debug_logger import get_logger
from core.queue import enqueue_process_invoice_upload
from db.pool import async_session
from models.invoice import Invoice
from models.uploaded_file import UploadedFile

logger = get_logger(__name__)


async def recover_stuck_invoice_uploads(openai_client: AsyncOpenAI | None) -> None:
    if openai_client is None:
        return

    async with async_session() as session:
        q = (
            select(UploadedFile.id, UploadedFile.uploaded_by, UploadedFile.uploaded_at)
            .outerjoin(Invoice, Invoice.source_file_id == UploadedFile.id)
            .where(
                UploadedFile.file_kind == "invoice",
                UploadedFile.processing_status.in_(("processing", "queued")),
                Invoice.id.is_(None),
            )
            .order_by(UploadedFile.id.desc())
            .limit(settings.max_startup_recovery_jobs)
        )
        rows = (await session.execute(q)).all()

    if not rows:
        return

    logger.info(
        "Recovering %d stuck invoice upload(s) on startup (limit=%d)",
        len(rows),
        settings.max_startup_recovery_jobs,
    )
    for upload_id, user_id, _uploaded_at in rows:
        try:
            enqueue_process_invoice_upload(upload_id, user_id)
        except Exception as exc:
            logger.warning(
                "Could not enqueue startup recovery for upload_id=%d: %s",
                upload_id,
                exc,
            )
