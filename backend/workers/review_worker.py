from __future__ import annotations

from core.debug_logger import get_logger
from core.queue import enqueue_enrich_review_task
from core.queue_names import TASK_ENRICH_REVIEW_TASK
from core.worker_locks import acquire_review_lock
from workers.base_worker import run_async_task

logger = get_logger(__name__)


def enrich_review_task(review_task_id: int, owner_user_id: int | None = None) -> None:
    """Legacy queue hook — Manual Review enriches tasks when listing via the API."""
    run_async_task(
        task_name=TASK_ENRICH_REVIEW_TASK,
        args={"review_task_id": review_task_id, "owner_user_id": owner_user_id},
        handler=lambda: _enrich_review_task(review_task_id),
        acquire_lock=lambda owner: acquire_review_lock(review_task_id, owner),
        requeue_rate_limited=lambda retry_count, delay_seconds: enqueue_enrich_review_task(
            review_task_id,
            owner_user_id=owner_user_id,
            retry_count=retry_count,
            delay_seconds=delay_seconds,
        ),
    )


async def _enrich_review_task(review_task_id: int) -> dict:
    logger.info(
        "Skipping review enrichment worker for task_id=%s (API list enriches on read)",
        review_task_id,
    )
    return {"review_task_id": review_task_id, "skipped": True}
