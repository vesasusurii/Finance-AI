import os
from unittest.mock import MagicMock

os.environ["DEBUG"] = "false"

from core.dlq import classify_failure
from core.queue_names import (
    TASK_ENRICH_REVIEW_TASK,
    TASK_MATCH_BANK_TRANSACTIONS,
    TASK_PROCESS_INVOICE_UPLOAD,
    queue_for_task,
)
from core.rate_limiter import OpenAIRateLease
from core.system_mode import current_system_mode
from core.worker_exceptions import RateLimitExceeded
from core.worker_locks import acquire_ocr_lock, acquire_transaction_lock
import core.queue_names as queue_names
import core.rate_limiter as rate_limiter
import core.system_mode as system_mode


def test_priority_routing_correctness(monkeypatch):
    monkeypatch.setattr(queue_names.settings, "queue_mode", "adaptive")
    monkeypatch.setattr(queue_names.settings, "rq_ocr_high_queue", "ocr_high_priority")
    monkeypatch.setattr(queue_names.settings, "rq_ocr_normal_queue", "ocr_normal")

    assert queue_for_task(TASK_PROCESS_INVOICE_UPLOAD, priority="high") == "ocr_high_priority"
    assert queue_for_task(TASK_PROCESS_INVOICE_UPLOAD, priority="high", retry_count=1) == "ocr_normal"
    assert queue_for_task(TASK_PROCESS_INVOICE_UPLOAD, priority="normal") == "ocr_normal"
    assert queue_for_task(TASK_ENRICH_REVIEW_TASK) == "review"
    assert queue_for_task(TASK_MATCH_BANK_TRANSACTIONS) == "transaction"


def test_rate_limit_lease_raises_without_failing_job(monkeypatch):
    redis = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [None, 99]
    redis.pipeline.return_value = pipe
    monkeypatch.setattr(rate_limiter.settings, "queue_mode", "adaptive")
    monkeypatch.setattr(rate_limiter.settings, "openai_rps_limit", 1)
    monkeypatch.setattr(rate_limiter, "get_redis_connection", lambda: redis)

    try:
        with OpenAIRateLease("gpt-4o-mini"):
            pass
    except RateLimitExceeded as exc:
        assert exc.retry_after_seconds > 0
    else:
        raise AssertionError("expected RateLimitExceeded")


def test_lock_prevents_duplicate_processing(monkeypatch):
    redis = MagicMock()
    redis.set.return_value = None
    monkeypatch.setattr("core.worker_locks.get_redis_connection", lambda: redis)

    lock = acquire_ocr_lock(123, "worker-1")

    assert lock is None
    redis.set.assert_called_once()


def test_transaction_lock_uses_statement_scope(monkeypatch):
    redis = MagicMock()
    redis.set.return_value = True
    monkeypatch.setattr("core.worker_locks.get_redis_connection", lambda: redis)

    lock = acquire_transaction_lock(42, "worker-1")

    assert lock == "lock:transaction:42"
    redis.set.assert_called_once_with("lock:transaction:42", "worker-1", nx=True, ex=3600)


def test_system_mode_degrades_under_backlog(monkeypatch):
    monkeypatch.setattr(system_mode.settings, "queue_mode", "adaptive")
    monkeypatch.setattr(system_mode.settings, "ocr_backlog_defer_threshold", 5000)
    monkeypatch.setattr(
        system_mode,
        "metrics_snapshot",
        lambda: {
            "ocr_queue_size": 6000,
            "failure_rate_5m": 0,
            "openai_avg_latency_ms": 0,
        },
    )

    assert current_system_mode() == "degraded"


def test_dlq_classification_accuracy():
    assert classify_failure(RateLimitExceeded("limited", retry_after_seconds=10)) == "rate_limit"
    assert classify_failure(TimeoutError("request timeout")) == "timeout"
    assert classify_failure(Exception("Password-protected PDF cannot be processed")) == "invalid_pdf"
    assert classify_failure(Exception("OpenAI upstream failed")) == "openai_failure"
