import os
from unittest.mock import MagicMock

os.environ["DEBUG"] = "false"

from config import settings
from core.queue_job_classifier import (
    classify_from_upload,
    classify_invoice_ocr_job,
)
from core.upload_enqueue import safe_enqueue_invoice_ocr
from core.worker_metrics import metrics_snapshot, record_task_metric
from core.worker_locks import acquire_ocr_lock, release_lock


def test_small_jobs_receive_higher_priority(monkeypatch):
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", True)

    image = classify_invoice_ocr_job(mime="image/jpeg", page_count=1)
    assert image.queue_class == "small_fast_job"
    assert image.queue_priority == "high"

    digital = classify_invoice_ocr_job(
        mime="application/pdf",
        page_count=3,
        has_text_layer=True,
        text_chars=500,
    )
    assert digital.queue_class == "small_fast_job"
    assert digital.queue_priority == "high"
    assert digital.queue_priority_reason == "digital_pdf_text_layer"

    large = classify_invoice_ocr_job(
        mime="application/pdf",
        page_count=8,
        has_text_layer=False,
        file_size=3_000_000,
    )
    assert large.queue_class == "large_slow_job"
    assert large.queue_priority == "normal"


def test_large_jobs_receive_starvation_boost(monkeypatch):
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", True)
    monkeypatch.setattr(settings, "openai_queue_starvation_boost_seconds", 60)

    waiting = classify_invoice_ocr_job(
        mime="application/pdf",
        page_count=10,
        has_text_layer=False,
        uploaded_age_seconds=120,
    )
    assert waiting.queue_class == "large_slow_job"
    assert waiting.queue_priority == "high"
    assert waiting.queue_priority_reason == "starvation_boost"
    assert waiting.queue_starvation_boosted is True


def test_duplicate_cache_and_reprocess_highest_priority(monkeypatch):
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", True)

    cache_hit = classify_invoice_ocr_job(
        mime="application/pdf",
        page_count=20,
        duplicate_cache_hit=True,
    )
    assert cache_hit.queue_priority == "high"
    assert cache_hit.queue_priority_reason == "duplicate_cache_hit"

    reprocess = classify_invoice_ocr_job(
        mime="application/pdf",
        page_count=20,
        duplicate_reprocess=True,
    )
    assert reprocess.queue_priority == "high"
    assert reprocess.queue_priority_reason == "duplicate_reprocess"


def test_disabled_flag_keeps_legacy_priority(monkeypatch):
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", False)

    single = classify_invoice_ocr_job(
        mime="image/jpeg",
        page_count=1,
        explicit_priority="normal",
        batch_upload=False,
    )
    assert single.queue_class == "normal_job"
    assert single.queue_priority == "normal"
    assert single.queue_priority_reason == "legacy_priority"

    batch = classify_invoice_ocr_job(
        mime="image/jpeg",
        page_count=1,
        explicit_priority=None,
        batch_upload=True,
    )
    assert batch.queue_priority == "normal"


def test_classify_from_upload_records_metadata(monkeypatch):
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", True)
    monkeypatch.setattr(
        "core.queue_job_classifier.inspect_upload_content",
        lambda _content, _mime: (1, True, 400),
    )

    result = classify_from_upload(
        mime="application/pdf",
        file_size=1200,
        content=b"%PDF",
        duplicate_reprocess=False,
    )

    meta = result.metadata()
    assert meta["queue_class"] == "small_fast_job"
    assert meta["queue_priority"] == "high"
    assert meta["queue_priority_reason"] == "single_page_or_image"
    assert meta["queue_starvation_boosted"] is False


def test_safe_enqueue_writes_queue_metadata(monkeypatch):
    monkeypatch.setattr(settings, "queue_mode", "rq")
    monkeypatch.setattr(settings, "openai_queue_prioritization_enabled", True)
    progress_updates: list[dict] = []
    monkeypatch.setattr(
        "core.upload_enqueue.update_ocr_progress",
        lambda upload_id, **fields: progress_updates.append(
            {"upload_id": upload_id, **fields}
        ),
    )
    monkeypatch.setattr("core.upload_enqueue.store_upload_bytes", lambda *_args: None)
    monkeypatch.setattr(
        "core.upload_enqueue.enqueue_process_invoice_upload",
        lambda upload_id, user_id, priority: None,
    )

    safe_enqueue_invoice_ocr(
        42,
        7,
        mime="image/png",
        file_size=500,
        content=b"png-bytes",
    )

    assert progress_updates
    fields = progress_updates[0]
    assert fields["upload_id"] == 42
    assert fields["queue_class"] == "small_fast_job"
    assert fields["queue_priority"] == "high"
    assert fields["queued_at"] is not None


def test_worker_metrics_queue_class_distribution(monkeypatch):
    redis = MagicMock()
    redis.zrangebyscore.return_value = [
        b"1|process_invoice_upload|ocr_high|5000|completed|1000|small_fast_job|120",
        b"2|process_invoice_upload|ocr_normal|30000|completed|8000|large_slow_job|45000",
        b"3|process_invoice_upload|ocr_high|4000|completed|900|small_fast_job|80",
    ]
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)
    monkeypatch.setattr("core.worker_metrics.queue_size", lambda _name: 0)
    monkeypatch.setattr(
        "core.worker_metrics.openai_avg_from_recent_timings",
        lambda: None,
    )

    metrics = metrics_snapshot()

    assert metrics["queue_class_distribution"] == {
        "small_fast_job": 2,
        "large_slow_job": 1,
    }
    assert metrics["avg_queue_wait_ms_by_class"]["small_fast_job"] == 100.0
    assert metrics["avg_queue_wait_ms_by_class"]["large_slow_job"] == 45000.0


def test_no_duplicate_processing_when_lock_held():
    owner_a = "worker:a"
    owner_b = "worker:b"
    upload_id = 9001

    first = acquire_ocr_lock(upload_id, owner_a)
    assert first is not None
    second = acquire_ocr_lock(upload_id, owner_b)
    assert second is None

    release_lock(first, owner_a)
    third = acquire_ocr_lock(upload_id, owner_b)
    assert third is not None
    release_lock(third, owner_b)


def test_record_task_metric_includes_queue_fields(monkeypatch):
    redis = MagicMock()
    captured: dict = {}
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)

    def _zadd(_key, mapping):
        captured["entry"] = next(iter(mapping))

    redis.zadd.side_effect = _zadd

    record_task_metric(
        job_type="process_invoice_upload",
        queue_name="ocr_high",
        duration_ms=1200.0,
        status="completed",
        openai_latency_ms=400.0,
        queue_class="small_fast_job",
        queue_wait_ms=55.0,
    )

    assert "small_fast_job" in captured["entry"]
    assert captured["entry"].endswith("|55.0")
