import os

os.environ["DEBUG"] = "false"

from unittest.mock import MagicMock

import pytest

from core.ocr_progress import (
    normalize_ocr_timing_fields,
    openai_avg_from_recent_timings,
    record_recent_ocr_timing,
    recent_ocr_timings,
)
from core.worker_metrics import metrics_snapshot


def test_normalize_ocr_timing_fields_download_alias():
    row = normalize_ocr_timing_fields({"storage_download_ms": 42.5})
    assert row["download_ms"] == 42.5
    assert row["storage_download_ms"] == 42.5
    assert row["openai_call_count"] is None
    assert row["extraction_mode"] is None
    assert "queue_wait_ms" in row


def test_normalize_ocr_timing_fields_openai_call_count():
    row = normalize_ocr_timing_fields(
        {"openai_calls": [{"openai_ms": 10.0}, {"openai_ms": 20.0}]}
    )
    assert row["openai_call_count"] == 2


def test_recent_ocr_timings_normalized(monkeypatch):
    redis = MagicMock()
    payload = (
        '{"upload_id": 1, "openai_total_ms": 5000.0, "storage_download_ms": 12.0}'
    )
    redis.zrevrange.return_value = [payload.encode("utf-8")]
    monkeypatch.setattr("core.ocr_progress.get_redis_connection", lambda: redis)

    rows = recent_ocr_timings(limit=1)

    assert rows[0]["download_ms"] == 12.0
    assert rows[0]["openai_total_ms"] == 5000.0
    assert rows[0]["extraction_mode"] is None


def test_openai_avg_from_recent_timings(monkeypatch):
    monkeypatch.setattr(
        "core.ocr_progress.recent_ocr_timings",
        lambda limit=20: [
            {"openai_total_ms": 4000.0},
            {"openai_total_ms": 6000.0},
        ],
    )
    assert openai_avg_from_recent_timings() == 5000.0


def test_metrics_snapshot_separates_worker_and_openai(monkeypatch):
    redis = MagicMock()
    redis.zrangebyscore.return_value = [
        b"1|process_invoice_upload|ocr_normal|30000|completed|12000",
        b"2|process_invoice_upload|ocr_normal|25000|completed|8000",
    ]
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)
    monkeypatch.setattr(
        "core.worker_metrics.queue_size",
        lambda _name: 0,
    )
    monkeypatch.setattr(
        "core.worker_metrics.openai_avg_from_recent_timings",
        lambda: None,
    )

    metrics = metrics_snapshot()

    assert metrics["worker_avg_duration_ms"] == 27500.0
    assert metrics["ocr_avg_duration_ms"] == 27500.0
    assert metrics["openai_avg_latency_ms"] == 10000.0


def test_metrics_snapshot_openai_fallback_to_recent(monkeypatch):
    redis = MagicMock()
    redis.zrangebyscore.return_value = [
        b"1|process_invoice_upload|ocr_normal|30000|completed|",
    ]
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)
    monkeypatch.setattr("core.worker_metrics.queue_size", lambda _name: 0)
    monkeypatch.setattr(
        "core.worker_metrics.openai_avg_from_recent_timings",
        lambda: 4500.0,
    )

    metrics = metrics_snapshot()

    assert metrics["worker_avg_duration_ms"] == 30000.0
    assert metrics["openai_avg_latency_ms"] == 4500.0
