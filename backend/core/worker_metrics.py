from __future__ import annotations

import time
from collections import defaultdict
from statistics import mean

from rq import Queue

from config import settings
from core.ocr_metrics import build_ocr_analytics
from core.ocr_progress import openai_avg_from_recent_timings, pipeline_overlap_avg_from_recent_timings
from core.queue_names import all_queue_names
from core.redis_client import get_redis_connection


def record_task_metric(
    *,
    job_type: str,
    queue_name: str,
    duration_ms: float,
    status: str,
    openai_latency_ms: float | None = None,
    queue_class: str | None = None,
    queue_wait_ms: float | None = None,
) -> None:
    redis = get_redis_connection()
    now = time.time()
    entry = (
        f"{now}|{job_type}|{queue_name}|{duration_ms}|{status}|"
        f"{openai_latency_ms if openai_latency_ms is not None else ''}|"
        f"{queue_class or ''}|"
        f"{queue_wait_ms if queue_wait_ms is not None else ''}"
    )
    key = "metrics:workers:tasks"
    redis.zadd(key, {entry: now})
    redis.zremrangebyscore(key, 0, now - settings.worker_metrics_window_seconds)
    redis.expire(key, settings.worker_metrics_window_seconds * 2)


def _parse_task_row(text: str) -> dict | None:
    parts = text.split("|")
    if len(parts) < 6:
        return None
    row: dict = {
        "job_type": parts[1],
        "queue_name": parts[2],
        "duration_ms": parts[3],
        "status": parts[4],
        "openai_latency_ms": parts[5],
    }
    if len(parts) >= 7:
        row["queue_class"] = parts[6] or None
    if len(parts) >= 8:
        row["queue_wait_ms"] = parts[7] or None
    return row


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
    queue_class_counts: dict[str, int] = defaultdict(int)
    queue_wait_by_class: dict[str, list[float]] = defaultdict(list)
    total = 0
    for raw in rows:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        parsed = _parse_task_row(text)
        if parsed is None:
            continue
        total += 1
        if parsed["job_type"] == "process_invoice_upload":
            try:
                ocr_durations.append(float(parsed["duration_ms"]))
            except ValueError:
                pass
            queue_class = parsed.get("queue_class")
            if queue_class:
                queue_class_counts[queue_class] += 1
                wait_raw = parsed.get("queue_wait_ms")
                if wait_raw:
                    try:
                        queue_wait_by_class[queue_class].append(float(wait_raw))
                    except ValueError:
                        pass
        if parsed["status"] == "failed":
            failures += 1
        openai_raw = parsed.get("openai_latency_ms")
        if openai_raw:
            try:
                openai_latencies.append(float(openai_raw))
            except ValueError:
                pass
    sizes = {name: queue_size(name) for name in all_queue_names()}
    ocr_size = sizes.get(settings.rq_ocr_high_queue, 0) + sizes.get(
        settings.rq_ocr_normal_queue, 0
    )
    worker_avg = round(mean(ocr_durations), 1) if ocr_durations else 0
    openai_avg = round(mean(openai_latencies), 1) if openai_latencies else None
    if openai_avg is None:
        openai_avg = openai_avg_from_recent_timings() or 0
    avg_queue_wait_by_class = {
        name: round(mean(values), 1)
        for name, values in queue_wait_by_class.items()
        if values
    }
    overlap_avg = pipeline_overlap_avg_from_recent_timings()
    ocr_analytics = build_ocr_analytics()
    return {
        "ocr_queue_size": ocr_size,
        "ocr_high_priority_queue_size": sizes.get(settings.rq_ocr_high_queue, 0),
        "ocr_normal_queue_size": sizes.get(settings.rq_ocr_normal_queue, 0),
        "review_queue_size": sizes.get(settings.rq_review_queue, 0),
        "transaction_queue_size": sizes.get(settings.rq_transaction_queue, 0),
        # End-to-end worker job duration (queue + download + extract + persist).
        "ocr_avg_duration_ms": worker_avg,
        "worker_avg_duration_ms": worker_avg,
        "failure_rate_5m": round(failures / total, 4) if total else 0,
        # OpenAI API time only — not full worker duration.
        "openai_avg_latency_ms": openai_avg,
        "queue_class_distribution": dict(queue_class_counts),
        "avg_queue_wait_ms_by_class": avg_queue_wait_by_class,
        "avg_pipeline_overlap_saved_ms": overlap_avg or 0,
        "ocr_analytics": ocr_analytics,
    }
