from __future__ import annotations

from datetime import timedelta

from rq import Queue, Retry

from config import settings
from core.adaptive_backoff import adaptive_backoff_seconds
from core.queue_names import (
    TASK_ENRICH_REVIEW_TASK,
    TASK_MATCH_BANK_TRANSACTIONS,
    TASK_PROCESS_INVOICE_UPLOAD,
    queue_for_task,
)
from core.redis_client import get_redis_connection


TASK_HANDLERS = {
    TASK_PROCESS_INVOICE_UPLOAD: "workers.ocr_worker.process_invoice_upload",
    TASK_ENRICH_REVIEW_TASK: "workers.review_worker.enrich_review_task",
    TASK_MATCH_BANK_TRANSACTIONS: "workers.transaction_worker.match_bank_transactions",
}


def retry_intervals(*, retry_count: int = 0, openai_rate_limited: bool = False) -> list[int]:
    if settings.queue_mode != "adaptive":
        return [
            settings.task_retry_base_seconds * (2**attempt)
            for attempt in range(settings.task_max_retries)
        ]
    return [
        adaptive_backoff_seconds(
            retry_count + attempt,
            openai_rate_limited=openai_rate_limited,
        )
        for attempt in range(settings.task_max_retries)
    ]


def _enqueue_task(
    task_name: str,
    *args,
    priority: str | None = None,
    retry_count: int = 0,
    delay_seconds: int | None = None,
) -> str:
    handler = TASK_HANDLERS[task_name]
    queue_name = queue_for_task(
        task_name,
        priority=priority,
        retry_count=retry_count,
    )
    queue = Queue(queue_name, connection=get_redis_connection())
    retry = Retry(
        max=settings.task_max_retries,
        interval=retry_intervals(retry_count=retry_count),
    )
    kwargs = {
        "retry": retry,
        "job_timeout": "30m",
        "result_ttl": 3600,
        "failure_ttl": 86400,
    }
    if delay_seconds and delay_seconds > 0:
        rq_job = queue.enqueue_in(
            timedelta(seconds=delay_seconds),
            handler,
            *args,
            **kwargs,
        )
    else:
        rq_job = queue.enqueue(handler, *args, **kwargs)
    return rq_job.id


def enqueue_process_invoice_upload(
    upload_id: int,
    user_id: int,
    *,
    priority: str | None = None,
    retry_count: int = 0,
    delay_seconds: int | None = None,
) -> str:
    return _enqueue_task(
        TASK_PROCESS_INVOICE_UPLOAD,
        upload_id,
        user_id,
        priority=priority,
        retry_count=retry_count,
        delay_seconds=delay_seconds,
    )


def enqueue_enrich_review_task(
    review_task_id: int,
    *,
    owner_user_id: int | None = None,
    retry_count: int = 0,
    delay_seconds: int | None = None,
) -> str:
    return _enqueue_task(
        TASK_ENRICH_REVIEW_TASK,
        review_task_id,
        owner_user_id,
        retry_count=retry_count,
        delay_seconds=delay_seconds,
    )


def enqueue_match_bank_transactions(
    bank_statement_id: int | None,
    *,
    owner_user_id: int | None = None,
    retry_count: int = 0,
    delay_seconds: int | None = None,
) -> str:
    return _enqueue_task(
        TASK_MATCH_BANK_TRANSACTIONS,
        bank_statement_id,
        owner_user_id,
        retry_count=retry_count,
        delay_seconds=delay_seconds,
    )
