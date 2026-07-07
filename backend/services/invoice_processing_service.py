"""Background invoice OCR in the API process (no separate worker)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Set

from config import settings
from core.debug_logger import get_logger
from core.processing_locks import acquire_ocr_lock, release_lock
from core.worker_exceptions import RateLimitExceeded
from services.ocr_upload_processor import (
    mark_upload_failed,
    process_invoice_upload_shared,
)

logger = get_logger(__name__)

_running_tasks: Set[asyncio.Task[None]] = set()


def schedule_invoice_ocr(
    upload_id: int,
    user_id: int,
    *,
    content: bytes | None = None,
) -> None:
    """Fire-and-forget OCR after upload commit. Must not raise to callers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning(
            "Cannot schedule OCR without a running event loop (upload_id=%d)",
            upload_id,
        )
        return
    task = loop.create_task(_run_with_retries(upload_id, user_id, content=content))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


async def _run_with_retries(
    upload_id: int,
    user_id: int,
    *,
    attempt: int = 0,
    content: bytes | None = None,
) -> None:
    lock_owner = f"ocr:{upload_id}:{time.time()}"
    lock_key = acquire_ocr_lock(upload_id, lock_owner)
    if lock_key is None:
        logger.info("Skipping duplicate OCR for upload_id=%d", upload_id)
        return
    try:
        await process_invoice_upload(upload_id, user_id, content=content)
    except RateLimitExceeded as exc:
        if attempt < settings.task_max_retries:
            await asyncio.sleep(exc.retry_after_seconds)
            await _run_with_retries(
                upload_id,
                user_id,
                attempt=attempt + 1,
                content=content,
            )
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


async def process_invoice_upload(
    upload_id: int,
    user_id: int,
    *,
    content: bytes | None = None,
) -> dict:
    return await process_invoice_upload_shared(upload_id, user_id, content=content)
