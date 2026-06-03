from __future__ import annotations

import time

from openai import AsyncOpenAI

from config import settings
from core.cache import cache
from core.cost_control import apply_ocr_cost_controls
from core.debug_logger import get_logger
from core.queue import enqueue_process_invoice_upload
from core.queue_names import TASK_PROCESS_INVOICE_UPLOAD
from core.rate_limiter import OpenAIRateLease
from core.system_mode import current_system_mode
from core.worker_locks import acquire_ocr_lock
from core.worker_storage import worker_storage_session
from db.pool import async_session
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import EXTRACTION_PROVIDER, InvoiceExtractionService
from workers.base_worker import run_async_task

logger = get_logger(__name__)


def process_invoice_upload(upload_id: int, user_id: int) -> None:
    run_async_task(
        task_name=TASK_PROCESS_INVOICE_UPLOAD,
        args={"upload_id": upload_id, "user_id": user_id},
        handler=lambda: _process_upload(upload_id, user_id),
        acquire_lock=lambda owner: acquire_ocr_lock(upload_id, owner),
        requeue_rate_limited=lambda retry_count, delay_seconds: enqueue_process_invoice_upload(
            upload_id,
            user_id,
            retry_count=retry_count,
            delay_seconds=delay_seconds,
        ),
    )


async def _process_upload(upload_id: int, user_id: int) -> dict:
    t0 = time.perf_counter()
    system_mode = current_system_mode()

    async with worker_storage_session():
        async with async_session() as session:
            invoice_repo = InvoiceRepository(session)
            upload_repo = UploadRepository(session)
            existing_invoice_id = await invoice_repo.get_id_by_source_file(upload_id)
            if existing_invoice_id is not None:
                await upload_repo.update_status(upload_id, "processed")
                await session.commit()
                cache.delete_pattern("review:*")
                cache.delete_pattern(f"ocr:upload:{upload_id}")
                return {
                    "upload_id": upload_id,
                    "invoice_id": existing_invoice_id,
                    "idempotent": True,
                }

            await upload_repo.update_status(upload_id, "processing")
            await session.commit()

            if not settings.openai_api_key:
                await upload_repo.update_status(upload_id, "failed")
                await session.commit()
                raise RuntimeError("OPENAI_API_KEY is not configured")

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = None
            try:
                with OpenAIRateLease(settings.openai_model), apply_ocr_cost_controls(
                    system_mode
                ):
                    extraction = InvoiceExtractionService(
                        upload_repo,
                        invoice_repo,
                        InvoiceAccessRepository(session),
                        AuditRepository(session),
                        AIValidationService(),
                        client,
                    )
                    response = await extraction.complete_upload(
                        upload_id, user_id, content=None
                    )
                await session.commit()
            except Exception:
                await session.commit()
                raise
            finally:
                await client.close()

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    cache.delete_pattern("review:*")
    cache.delete_pattern("bank_tx:*")
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
    return {
        "upload_id": upload_id,
        "invoice_id": response.invoice_id if response else None,
        "processing_status": response.processing_status if response else "failed",
        "duration_ms": duration_ms,
        "openai_latency_ms": duration_ms,
        "system_mode": system_mode,
    }
