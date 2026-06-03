from config import settings

TASK_PROCESS_INVOICE_UPLOAD = "process_invoice_upload"
TASK_ENRICH_REVIEW_TASK = "enrich_review_task"
TASK_MATCH_BANK_TRANSACTIONS = "match_bank_transactions"


def all_queue_names() -> list[str]:
    if settings.queue_mode != "adaptive":
        return [settings.rq_default_queue]
    return [
        settings.rq_ocr_high_queue,
        settings.rq_ocr_normal_queue,
        settings.rq_review_queue,
        settings.rq_transaction_queue,
    ]


def queue_for_task(
    task_name: str,
    *,
    priority: str | None = None,
    retry_count: int = 0,
) -> str:
    if settings.queue_mode != "adaptive":
        return settings.rq_default_queue
    if task_name == TASK_PROCESS_INVOICE_UPLOAD:
        if retry_count > 0:
            return settings.rq_ocr_normal_queue
        return (
            settings.rq_ocr_high_queue
            if str(priority or "").lower() == "high"
            else settings.rq_ocr_normal_queue
        )
    if task_name == TASK_ENRICH_REVIEW_TASK:
        return settings.rq_review_queue
    if task_name == TASK_MATCH_BANK_TRANSACTIONS:
        return settings.rq_transaction_queue
    return settings.rq_default_queue
