import os
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ["DEBUG"] = "false"

from config import settings
from schemas.invoice import ExtractionResult
from services.pipeline_overlap_service import (
    PipelineOverlapTracker,
    build_persistence_prep,
    build_validation_prep,
    run_parallel,
)


@pytest.mark.asyncio
async def test_run_parallel_records_saved_ms():
    tracker = PipelineOverlapTracker(enabled=True)

    async def primary():
        return "primary"

    async def overlap():
        return "overlap"

    result, overlap_result = await run_parallel(
        primary,
        overlap,
        section="test_section",
        tracker=tracker,
    )

    assert result == "primary"
    assert overlap_result == "overlap"
    assert "test_section" in tracker.tasks
    assert tracker.saved_ms >= 0


def test_build_persistence_prep_hash():
    prep = build_persistence_prep(b"invoice-bytes")
    assert prep.content_hash is not None
    assert prep.audit_action == "invoice_extracted"


def test_build_validation_prep_from_partials():
    partials = [
        ExtractionResult(
            invoice_number="INV-1",
            confidence_score=0.9,
        ),
        ExtractionResult(
            amount=100.0,
            confidence_score=0.8,
        ),
    ]
    prep = build_validation_prep(partials)
    assert prep.partial_count == 2
    assert prep.fields_present >= 2
    assert prep.confidence_scores == [0.9, 0.8]


def test_tracker_metadata():
    tracker = PipelineOverlapTracker(enabled=True)
    tracker.tasks.append("persistence_prep")
    tracker.record_parallel("vision_persistence_prep", 100.0, 40.0)
    meta = tracker.metadata()
    assert meta["pipeline_overlap_enabled"] is True
    assert meta["pipeline_overlap_saved_ms"] == 40.0
    assert meta["pipeline_overlap_fallback"] is False
    assert "vision_persistence_prep" in meta["pipeline_parallel_sections"]


@pytest.mark.asyncio
async def test_sequential_mode_when_overlap_disabled(monkeypatch):
    monkeypatch.setattr(settings, "openai_pipeline_overlap_enabled", False)
    from services.invoice_extraction_service import InvoiceExtractionService

    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=MagicMock(),
        openai_client=MagicMock(),
    )
    service._reset_pipeline_overlap(b"pdf")
    assert service._pipeline_overlap.enabled is False

    called = {"vision": False}

    async def fake_vision(*_args, **_kwargs):
        called["vision"] = True
        return ExtractionResult(invoice_number="X")

    service._openai_vision_extract = fake_vision  # type: ignore[method-assign]

    result = await service._openai_vision_call(
        [(b"img", "image/jpeg")],
        filename="test.pdf",
        file_type="pdf",
        model="gpt-4o-mini",
        page_range=(1, 1),
        total_pages=1,
    )
    assert called["vision"] is True
    assert result.invoice_number == "X"


@pytest.mark.asyncio
async def test_parallel_mode_produces_identical_json(monkeypatch):
    monkeypatch.setattr(settings, "openai_pipeline_overlap_enabled", True)
    from services.invoice_extraction_service import InvoiceExtractionService

    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=MagicMock(),
        openai_client=MagicMock(),
    )
    service._reset_pipeline_overlap(b"pdf")
    expected = ExtractionResult(invoice_number="INV-99", amount=42.0)

    async def fake_vision(*_args, **_kwargs):
        return expected.model_copy(deep=True)

    service._openai_vision_extract = fake_vision  # type: ignore[method-assign]

    result = await service._openai_vision_call(
        [(b"img", "image/jpeg")],
        filename="test.pdf",
        file_type="pdf",
        model="gpt-4o-mini",
        page_range=(1, 1),
        total_pages=1,
    )
    assert result.model_dump() == expected.model_dump()
    assert service._pipeline_overlap.persistence_prep is not None


@pytest.mark.asyncio
async def test_overlap_failure_falls_back(monkeypatch):
    tracker = PipelineOverlapTracker(enabled=True)

    async def primary():
        return "ok"

    async def overlap():
        raise RuntimeError("prep failed")

    with pytest.raises(RuntimeError):
        await run_parallel(primary, overlap, section="fail", tracker=tracker)


def test_pipeline_overlap_avg_from_recent_timings(monkeypatch):
    monkeypatch.setattr(
        "core.ocr_progress.recent_ocr_timings",
        lambda limit=20: [
            {"pipeline_overlap_saved_ms": 100.0},
            {"pipeline_overlap_saved_ms": 200.0},
        ],
    )
    from core.ocr_progress import pipeline_overlap_avg_from_recent_timings

    assert pipeline_overlap_avg_from_recent_timings() == 150.0


def test_metrics_snapshot_includes_overlap_avg(monkeypatch):
    redis = MagicMock()
    redis.zrangebyscore.return_value = []
    monkeypatch.setattr("core.worker_metrics.get_redis_connection", lambda: redis)
    monkeypatch.setattr("core.worker_metrics.queue_size", lambda _name: 0)
    monkeypatch.setattr(
        "core.worker_metrics.openai_avg_from_recent_timings",
        lambda: None,
    )
    monkeypatch.setattr(
        "core.worker_metrics.pipeline_overlap_avg_from_recent_timings",
        lambda: 75.5,
    )
    from core.worker_metrics import metrics_snapshot

    metrics = metrics_snapshot()
    assert metrics["avg_pipeline_overlap_saved_ms"] == 75.5
