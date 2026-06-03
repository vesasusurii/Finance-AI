from __future__ import annotations

import time
from statistics import mean

from rq import Queue

from config import settings
from core.queue_names import all_queue_names
from core.redis_client import get_redis_connection


def record_task_metric(
    *,
    job_type: str,
    queue_name: str,
    duration_ms: float,
    status: str,
    openai_latency_ms: float | None = None,
) -> None:
    redis = get_redis_connection()
    now = time.time()
    entry = (
        f"{now}|{job_type}|{queue_name}|{duration_ms}|{status}|"
        f"{openai_latency_ms if openai_latency_ms is not None else ''}"
    )
    key = "metrics:workers:tasks"
    redis.zadd(key, {entry: now})
    redis.zremrangebyscore(key, 0, now - settings.worker_metrics_window_seconds)
    redis.expire(key, settings.worker_metrics_window_seconds * 2)


def queue_size(queue_name: str) -> int:
    return len(Queue(queue_name, connection=get_redis_connection()))


def metrics_snapshot() -> dict:
    redis = get_redis_connection()
    now = time.time()
    rows = redis.zrangebyscore(
        "metrics:workers:tasks",
        now - settings.worker_metrics_window_seconds,
        now,
    )
    ocr_durations: list[float] = []
    failures = 0
    openai_latencies: list[float] = []
    total = 0
    for raw in rows:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        parts = text.split("|")
        if len(parts) < 6:
            continue
        total += 1
        if parts[1] == "process_invoice_upload":
            try:
                ocr_durations.append(float(parts[3]))
            except ValueError:
                pass
        if parts[4] == "failed":
            failures += 1
        if parts[5]:
            try:
                openai_latencies.append(float(parts[5]))
            except ValueError:
                pass
    sizes = {name: queue_size(name) for name in all_queue_names()}
    ocr_size = sizes.get(settings.rq_ocr_high_queue, 0) + sizes.get(
        settings.rq_ocr_normal_queue, 0
    )
    return {
        "ocr_queue_size": ocr_size,
        "ocr_high_priority_queue_size": sizes.get(settings.rq_ocr_high_queue, 0),
        "ocr_normal_queue_size": sizes.get(settings.rq_ocr_normal_queue, 0),
        "review_queue_size": sizes.get(settings.rq_review_queue, 0),
        "transaction_queue_size": sizes.get(settings.rq_transaction_queue, 0),
        "ocr_avg_duration_ms": round(mean(ocr_durations), 1) if ocr_durations else 0,
        "failure_rate_5m": round(failures / total, 4) if total else 0,
        "openai_avg_latency_ms": round(mean(openai_latencies), 1)
        if openai_latencies
        else 0,
    }
