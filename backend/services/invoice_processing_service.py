"""Background invoice OCR in the API process (no separate worker)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Set

from openai import AsyncOpenAI

from config import settings
from core.cache import cache
from core.cost_control import apply_ocr_cost_controls
from core.debug_logger import get_logger
from core.processing_locks import acquire_ocr_lock, release_lock
from core.rate_limit_exceptions import RateLimitExceeded
from core.rate_limiter import OpenAIRateLease
from core.system_mode import current_system_mode
from db.pool import async_session
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import EXTRACTION_PROVIDER, InvoiceExtractionService

logger = get_logger(__name__)

_running_tasks: Set[asyncio.Task[None]] = set()


def schedule_invoice_ocr(upload_id: int, user_id: int) -> None:
    """Fire-and-forget OCR after upload commit. Must not raise to callers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "Cannot schedule OCR without a running event loop (upload_id=%d)",
            upload_id,
        )
        return
    task = loop.create_task(_run_with_retries(upload_id, user_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def _run_with_retries(
    upload_id: int,
    user_id: int,
    *,
    attempt: int = 0,
) -> None:
    lock_owner = f"ocr:{upload_id}:{time.time()}"
    lock_key = acquire_ocr_lock(upload_id, lock_owner)
    if lock_key is None:
        logger.info("Skipping duplicate OCR for upload_id=%d", upload_id)
        return
    try:
        await process_invoice_upload(upload_id, user_id)
    except RateLimitExceeded as exc:
        if attempt < settings.task_max_retries:
            await asyncio.sleep(exc.retry_after_seconds)
            await _run_with_retries(upload_id, user_id, attempt=attempt + 1)
        else:
            logger.warning(
                "OCR rate-limited upload_id=%d after %d attempts",
                upload_id,
                attempt + 1,
            )
    except Exception:
        logger.exception("OCR failed for upload_id=%d", upload_id)
    finally:
        release_lock(lock_key, lock_owner)


async def process_invoice_upload(upload_id: int, user_id: int) -> dict:
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
        "system_mode": system_mode,
    }
