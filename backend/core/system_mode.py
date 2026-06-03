from __future__ import annotations

from config import settings
from core.worker_metrics import metrics_snapshot


def current_system_mode() -> str:
    if settings.queue_mode != "adaptive":
        return "normal"
    metrics = metrics_snapshot()
    ocr_backlog = int(metrics.get("ocr_queue_size") or 0)
    failure_rate = float(metrics.get("failure_rate_5m") or 0)
    openai_latency = float(metrics.get("openai_avg_latency_ms") or 0)
    if ocr_backlog >= settings.ocr_backlog_defer_threshold or failure_rate >= 0.15:
        return "degraded"
    if ocr_backlog >= settings.ocr_backlog_defer_threshold // 2 or openai_latency >= 20000:
        return "stressed"
    return "normal"
