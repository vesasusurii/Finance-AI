"""Background invoice OCR — runs after the upload HTTP response is returned."""

from __future__ import annotations

import asyncio

from fastapi import BackgroundTasks
from openai import AsyncOpenAI

from core.debug_logger import get_logger
from db.pool import async_session
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import InvoiceExtractionService

logger = get_logger(__name__)

_UPLOAD_VISIBLE_ATTEMPTS = 10
_UPLOAD_VISIBLE_DELAY_SECONDS = 0.3


def schedule_invoice_extraction(
    upload_id: int,
    user_id: int,
    openai_client: AsyncOpenAI | None,
    background_tasks: BackgroundTasks,
) -> None:
    """Queue OCR after the upload transaction commits and the response is sent."""
    background_tasks.add_task(
        _run_invoice_extraction, upload_id, user_id, openai_client
    )


async def _wait_for_upload_row(
    upload_id: int,
) -> bool:
    for attempt in range(_UPLOAD_VISIBLE_ATTEMPTS):
        async with async_session() as session:
            row = await UploadRepository(session).get(upload_id)
            if row is not None:
                return True
        if attempt + 1 < _UPLOAD_VISIBLE_ATTEMPTS:
            await asyncio.sleep(_UPLOAD_VISIBLE_DELAY_SECONDS)
    return False


async def _run_invoice_extraction(
    upload_id: int,
    user_id: int,
    openai_client: AsyncOpenAI | None,
) -> None:
    if not await _wait_for_upload_row(upload_id):
        logger.error(
            "Upload row upload_id=%d not visible after retries", upload_id
        )
        async with async_session() as fail_session:
            try:
                await UploadRepository(fail_session).update_status(
                    upload_id, "failed"
                )
                await fail_session.commit()
            except Exception:
                await fail_session.rollback()
        return

    async with async_session() as session:
        extraction = InvoiceExtractionService(
            UploadRepository(session),
            InvoiceRepository(session),
            InvoiceAccessRepository(session),
            AuditRepository(session),
            AIValidationService(),
            openai_client,
        )
        try:
            await extraction.complete_upload(upload_id, user_id)
            await session.commit()
            logger.info("Background extraction finished for upload_id=%d", upload_id)
        except Exception:
            await session.rollback()
            logger.exception(
                "Background extraction failed for upload_id=%d", upload_id
            )
            async with async_session() as fail_session:
                try:
                    await UploadRepository(fail_session).update_status(
                        upload_id, "failed"
                    )
                    await fail_session.commit()
                except Exception:
                    await fail_session.rollback()
                    logger.exception(
                        "Could not mark upload_id=%d as failed", upload_id
                    )
