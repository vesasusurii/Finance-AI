"""Shared OCR upload processing for inline and RQ worker execution."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from openai import AsyncOpenAI

from config import settings
from core.cache import cache
from core.cost_control import apply_ocr_cost_controls
from core.debug_logger import get_logger
from core.ocr_progress import get_ocr_progress, update_ocr_progress
from core.rate_limiter import OpenAIRateLease
from core.system_mode import current_system_mode
from core.worker_storage import worker_storage_session
from db.pool import async_session
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import EXTRACTION_PROVIDER, InvoiceExtractionService

logger = get_logger(__name__)


@asynccontextmanager
async def _no_worker_storage():
    yield


async def mark_upload_failed(upload_id: int) -> None:
    async with async_session() as session:
        await UploadRepository(session).update_status(upload_id, "failed")
        await session.commit()


def _openai_latency_ms(upload_id: int) -> float | None:
    progress = get_ocr_progress(upload_id)
    openai_total_ms = progress.get("openai_total_ms")
    try:
        return float(openai_total_ms) if openai_total_ms is not None else None
    except (TypeError, ValueError):
        return None


async def process_invoice_upload_shared(
    upload_id: int,
    user_id: int,
    *,
    content: bytes | None = None,
    content_provider: Callable[[], bytes | None] | None = None,
    use_worker_storage: bool = False,
) -> dict:
    t0 = time.perf_counter()
    system_mode = current_system_mode()

    async with async_session() as session:
        invoice_repo = InvoiceRepository(session)
        upload_repo = UploadRepository(session)
        existing_invoice_id = await invoice_repo.get_id_by_source_file(upload_id)
        if existing_invoice_id is not None:
            await upload_repo.update_status(upload_id, "processed")
            await session.commit()
            cache.delete_pattern("review:*")
            cache.delete_pattern("invoice_tab_counts:*")
            cache.delete_pattern(f"ocr:upload:{upload_id}")
            return {
                "upload_id": upload_id,
                "invoice_id": existing_invoice_id,
                "idempotent": True,
            }

        await upload_repo.update_status(upload_id, "processing")
        await session.commit()

    update_ocr_progress(
        upload_id,
        stage="processing",
        stage_label="Preparing extraction",
        upload_status="processing",
        model=settings.openai_model,
    )

    if not settings.openai_api_key:
        await mark_upload_failed(upload_id)
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = None
    storage_context = worker_storage_session() if use_worker_storage else _no_worker_storage()
    try:
        with OpenAIRateLease(settings.openai_model), apply_ocr_cost_controls(system_mode):
            async with storage_context:
                upload_content = content_provider() if content_provider else content
                async with async_session() as session:
                    extraction = InvoiceExtractionService(
                        UploadRepository(session),
                        InvoiceRepository(session),
                        InvoiceAccessRepository(session),
                        AuditRepository(session),
                        AIValidationService(),
                        client,
                    )
                    response = await extraction.complete_upload(
                        upload_id,
                        user_id,
                        content=upload_content,
                    )
                    await session.commit()
    finally:
        await client.close()

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    openai_latency_ms = _openai_latency_ms(upload_id)
    cache.delete_pattern("review:*")
    cache.delete_pattern("bank_tx:*")
    cache.delete_pattern("invoice_tab_counts:*")
    cache.delete_pattern("matching_tab_counts:*")
    cache.delete_pattern(f"ocr:upload:{upload_id}")
    logger.info(
        {
            "upload_id": upload_id,
            "duration_ms": duration_ms,
            "status": "completed",
            "model_provider": EXTRACTION_PROVIDER,
            "model": settings.openai_model,
            "system_mode": system_mode,
            "invoice_id": response.invoice_id if response else None,
        }
    )
    update_ocr_progress(
        upload_id,
        stage="processed",
        stage_label="Invoice saved",
        upload_status="processed",
        duration_ms=duration_ms,
        invoice_id=response.invoice_id if response else None,
    )
    return {
        "upload_id": upload_id,
        "invoice_id": response.invoice_id if response else None,
        "processing_status": response.processing_status if response else "failed",
        "duration_ms": duration_ms,
        "openai_total_ms": openai_latency_ms,
        "openai_latency_ms": openai_latency_ms,
        "system_mode": system_mode,
    }
