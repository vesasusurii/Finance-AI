from __future__ import annotations

from config import settings
from core.system_mode import current_system_mode
from core.worker_metrics import metrics_snapshot


def should_defer_ocr_enqueue() -> bool:
    if settings.queue_mode != "adaptive":
        return False
    metrics = metrics_snapshot()
    if int(metrics.get("ocr_queue_size") or 0) > settings.ocr_backlog_defer_threshold:
        return True
    if current_system_mode() == "degraded":
        return True
    return False


def defer_delay_seconds() -> int:
    return max(60, settings.ocr_avg_wait_defer_seconds)
