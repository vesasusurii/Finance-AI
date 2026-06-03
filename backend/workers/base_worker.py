from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from rq import get_current_job

from config import settings
from core.dlq import record_dlq_entry
from core.debug_logger import get_logger
from core.system_mode import current_system_mode
from core.worker_exceptions import RateLimitExceeded
from core.worker_locks import release_lock
from core.worker_metrics import record_task_metric

logger = get_logger(__name__)


def run_async_task(
    *,
    task_name: str,
    args: dict,
    handler: Callable[[], Awaitable[dict | None]],
    acquire_lock: Callable[[str], str | None] | None = None,
    requeue_rate_limited: Callable[[int, int], str] | None = None,
) -> None:
    asyncio.run(
        _run(
            task_name=task_name,
            args=args,
            handler=handler,
            acquire_lock=acquire_lock,
            requeue_rate_limited=requeue_rate_limited,
        )
    )


async def _run(
    *,
    task_name: str,
    args: dict,
    handler: Callable[[], Awaitable[dict | None]],
    acquire_lock: Callable[[str], str | None] | None,
    requeue_rate_limited: Callable[[int, int], str] | None,
) -> None:
    started = time.perf_counter()
    rq_job = get_current_job()
    rq_task_id = getattr(rq_job, "id", None)
    queue_name = getattr(rq_job, "origin", None) or settings.rq_default_queue
    attempt = int((getattr(rq_job, "meta", {}) or {}).get("attempt", 0))
    queue_wait_time_ms = 0.0
    enqueued_at = getattr(rq_job, "enqueued_at", None)
    if enqueued_at is not None:
        queue_wait_time_ms = round((time.time() - enqueued_at.timestamp()) * 1000, 1)
    if rq_job is not None:
        rq_job.meta["attempt"] = attempt + 1
        rq_job.save_meta()

    system_mode = current_system_mode()
    lock_owner = f"{task_name}:{rq_task_id or id(args)}:{time.time()}"
    lock_key = acquire_lock(lock_owner) if acquire_lock else None
    if acquire_lock is not None and lock_key is None:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            {
                "task_name": task_name,
                "rq_task_id": rq_task_id,
                "queue_name": queue_name,
                "attempt": attempt,
                "system_mode": system_mode,
                "queue_wait_time_ms": queue_wait_time_ms,
                "duration_ms": duration_ms,
                "status": "skipped_duplicate_lock",
            }
        )
        record_task_metric(
            job_type=task_name,
            queue_name=queue_name,
            duration_ms=duration_ms,
            status="completed",
        )
        return

    try:
        result = await handler()
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        openai_latency_ms = None
        if isinstance(result, dict):
            openai_latency_ms = result.get("openai_latency_ms") or result.get(
                "duration_ms"
            )
        record_task_metric(
            job_type=task_name,
            queue_name=queue_name,
            duration_ms=duration_ms,
            status="completed",
            openai_latency_ms=float(openai_latency_ms) if openai_latency_ms else None,
        )
        log_level = logger.info
        if task_name == "process_invoice_upload" and duration_ms > 45000:
            log_level = logger.error
        elif task_name == "process_invoice_upload" and duration_ms > 25000:
            log_level = logger.warning
        log_level(
            {
                "task_name": task_name,
                "rq_task_id": rq_task_id,
                "queue_name": queue_name,
                "attempt": attempt,
                "system_mode": system_mode,
                "openai_latency_ms": openai_latency_ms,
                "queue_wait_time_ms": queue_wait_time_ms,
                "duration_ms": duration_ms,
                "status": "completed",
                "result": result or {},
            }
        )
    except RateLimitExceeded as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        if requeue_rate_limited is not None:
            requeue_rate_limited(attempt + 1, exc.retry_after_seconds)
        record_task_metric(
            job_type=task_name,
            queue_name=queue_name,
            duration_ms=duration_ms,
            status="rate_limited",
        )
        logger.warning(
            {
                "task_name": task_name,
                "rq_task_id": rq_task_id,
                "queue_name": queue_name,
                "attempt": attempt,
                "system_mode": system_mode,
                "queue_wait_time_ms": queue_wait_time_ms,
                "duration_ms": duration_ms,
                "status": "rate_limited",
                "retry_after_seconds": exc.retry_after_seconds,
            }
        )
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        record_dlq_entry(
            task_name=task_name,
            args=args,
            exc=exc,
            retry_history=[{"attempt": attempt, "duration_ms": duration_ms}],
        )
        record_task_metric(
            job_type=task_name,
            queue_name=queue_name,
            duration_ms=duration_ms,
            status="failed",
        )
        logger.exception(
            {
                "task_name": task_name,
                "rq_task_id": rq_task_id,
                "queue_name": queue_name,
                "attempt": attempt,
                "system_mode": system_mode,
                "queue_wait_time_ms": queue_wait_time_ms,
                "duration_ms": duration_ms,
                "status": "failed",
                "failure_reason": str(exc),
            }
        )
        raise
    finally:
        release_lock(lock_key, lock_owner)
