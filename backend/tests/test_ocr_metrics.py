import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["DEBUG"] = "false"

from core.ocr_metrics import (
    SloConfig,
    build_ocr_analytics,
    classify_slowness,
    percentile,
    percentile_summary,
    slo_violations_for_job,
)
from core.worker_metrics import metrics_snapshot


def test_percentile_calculations():
    values = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]
    assert percentile(values, 50) == 500.0
    assert percentile(values, 90) == 900.0
    assert percentile(values, 99) == 1000.0
    summary = percentile_summary(values)
    assert summary["p50"] == 500.0
    assert summary["p95"] == 1000.0


def test_percentile_empty_does_not_crash():
    assert percentile([], 50) is None
    summary = percentile_summary([])
    assert summary["p50"] is None
    assert summary["p99"] is None


def test_build_ocr_analytics_empty():
    with patch("core.ocr_metrics.recent_ocr_timings", return_value=[]):
        analytics = build_ocr_analytics()
    assert analytics["sample_size"] == 0
    assert analytics["percentiles"]["total_ms"]["p50"] is None
    assert analytics["distributions"]["extraction_mode"] == {}
    assert analytics["slow_jobs"] == []
    assert analytics["slo_violations"] == []


def test_distributions_calculate_correctly():
    rows = [
        {
            "upload_id": 1,
            "total_ms": 5000.0,
            "openai_total_ms": 3000.0,
            "queue_wait_ms": 100.0,
            "render_ms": 500.0,
            "openai_call_count": 1,
            "extraction_mode": "vision_full_document",
            "preclassification_type": "digital_pdf",
            "prompt_strategy": "minimal",
            "image_detail_strategy": "adaptive_first_last_high",
            "merge_strategy": "deterministic",
            "render_strategy": "parallel",
            "model_strategy": "fast_only",
            "queue_class": "small_fast_job",
        },
        {
            "upload_id": 2,
            "total_ms": 12000.0,
            "openai_total_ms": 9000.0,
            "queue_wait_ms": 6000.0,
            "render_ms": 800.0,
            "merge_ms": 400.0,
            "openai_call_count": 4,
            "extraction_mode": "vision_batched_merge",
            "preclassification_type": "scanned_pdf",
            "prompt_strategy": "batch",
            "image_detail_strategy": "all_high",
            "merge_strategy": "llm",
            "render_strategy": "parallel",
            "model_strategy": "strong_fallback",
            "queue_class": "large_slow_job",
            "fallback_model_used": True,
            "targeted_recovery_used": True,
        },
    ]
    with patch("core.ocr_metrics.recent_ocr_timings", return_value=rows):
        analytics = build_ocr_analytics()

    assert analytics["sample_size"] == 2
    assert analytics["distributions"]["extraction_mode"]["vision_full_document"] == 1
    assert analytics["distributions"]["extraction_mode"]["vision_batched_merge"] == 1
    assert analytics["distributions"]["queue_class"]["small_fast_job"] == 1
    assert analytics["rates"]["targeted_recovery_usage"] == 0.5
    assert analytics["rates"]["fallback_usage"] == 0.5
    assert analytics["averages"]["openai_call_count"] == 2.5


def test_slow_job_classification():
    slo = SloConfig(8000, 6000, 5000, 3, 0.3)
    assert (
        classify_slowness(
            {"queue_wait_ms": 6000, "openai_total_ms": 1000, "openai_call_count": 1},
            slo,
        )
        == "queue_wait"
    )
    assert (
        classify_slowness(
            {"openai_total_ms": 7000, "openai_call_count": 1},
            slo,
        )
        == "openai_latency"
    )
    assert (
        classify_slowness(
            {"openai_call_count": 5},
            slo,
        )
        == "too_many_openai_calls"
    )
    assert (
        classify_slowness(
            {"fallback_model_used": True, "openai_call_count": 1},
            slo,
        )
        == "fallback_retry"
    )


def test_slo_violations_flagged():
    slo = SloConfig(8000, 6000, 5000, 3, 0.3)
    violations = slo_violations_for_job(
        {
            "total_ms": 9000,
            "openai_total_ms": 7000,
            "queue_wait_ms": 6000,
            "openai_call_count": 5,
        },
        slo,
    )
    assert violations == [
        "total_ms",
        "openai_total_ms",
        "queue_wait_ms",
        "openai_call_count",
    ]


def test_metrics_snapshot_backward_compatible(monkeypatch):
    redis = MagicMock()
    redis.zrangebyscore.return_value = [
        b"1|process_invoice_upload|ocr_normal|30000|completed|12000|small_fast_job|100",
    ]
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)
    monkeypatch.setattr("core.worker_metrics.queue_size", lambda _name: 2)
    monkeypatch.setattr(
        "core.worker_metrics.openai_avg_from_recent_timings",
        lambda: 5000.0,
    )
    monkeypatch.setattr(
        "core.worker_metrics.pipeline_overlap_avg_from_recent_timings",
        lambda: 50.0,
    )
    monkeypatch.setattr(
        "core.ocr_metrics.recent_ocr_timings",
        lambda limit=50: [{"upload_id": 1, "total_ms": 4000.0, "openai_total_ms": 3000.0}],
    )

    metrics = metrics_snapshot()

    assert metrics["ocr_queue_size"] == 4
    assert metrics["worker_avg_duration_ms"] == 30000.0
    assert metrics["openai_avg_latency_ms"] == 12000.0
    assert "ocr_analytics" in metrics
    assert metrics["ocr_analytics"]["sample_size"] == 1


def test_log_slo_violations_emits_warning():
    from core.ocr_metrics import log_slo_violations

    with patch("core.ocr_metrics.logger") as mock_logger:
        log_slo_violations(
            {
                "upload_id": 99,
                "total_ms": 15000,
                "openai_total_ms": 7000,
                "queue_wait_ms": 100,
                "openai_call_count": 1,
                "extraction_mode": "vision_full_document",
            }
        )
        mock_logger.warning.assert_called_once()
