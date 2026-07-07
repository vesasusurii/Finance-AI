from __future__ import annotations

from core.queue import enqueue_process_invoice_upload
from core.queue_names import TASK_PROCESS_INVOICE_UPLOAD
from core.upload_handoff import pop_upload_bytes
from core.worker_locks import acquire_ocr_lock
from services.ocr_upload_processor import process_invoice_upload_shared
from workers.base_worker import run_async_task


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
    return await process_invoice_upload_shared(
        upload_id,
        user_id,
        content_provider=lambda: pop_upload_bytes(upload_id),
        use_worker_storage=True,
    )
