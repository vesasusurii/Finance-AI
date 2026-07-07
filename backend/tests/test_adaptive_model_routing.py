"""Adaptive model routing tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from config import settings
from schemas.invoice import ExtractionResult
from services.adaptive_model_routing_service import AdaptiveModelRoutingService
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import InvoiceExtractionService


def _routing() -> AdaptiveModelRoutingService:
    return AdaptiveModelRoutingService(AIValidationService())


def _service() -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=MagicMock(),
    )


def test_text_hints_strategy_uses_no_model():
    meta = _routing().primary_metadata(mode="text_hints", model_used=None)
    assert meta["model_strategy"] == "none"
    assert meta["model_used"] is None


def test_text_llm_strategy_uses_fast_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-4o-mini")
    routing = _routing()
    meta = routing.primary_metadata(mode="text_llm", model_used=routing.fast_model())
    assert meta["model_strategy"] == "fast_text"
    assert meta["model_used"] == "gpt-4o-mini"


def test_vision_strategy_uses_fast_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-4o-mini")
    meta = _routing().primary_metadata(
        mode="vision_full_document",
        model_used="gpt-4o-mini",
    )
    assert meta["model_strategy"] == "fast_vision"
    assert meta["model_used"] == "gpt-4o-mini"


def test_valid_extraction_does_not_use_strong_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_strong_retry_enabled", True)
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_model_strong", "gpt-4o")

    result = ExtractionResult(
        invoice_number="INV-1",
        invoice_date="2026-05-01",
        amount=10.0,
        name_of_company="Acme",
        confidence_score=0.75,
    )
    should_retry, reasons = _routing().should_use_strong_fallback(
        result,
        {"extraction_mode": "vision_full_document"},
    )
    assert should_retry is False
    assert reasons == []


@pytest.mark.asyncio
async def test_strong_model_called_on_validation_failure(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    weak = ExtractionResult(confidence_score=0.95, needs_review=True)
    strong = ExtractionResult(
        invoice_number="007",
        amount=434.6,
        invoice_date="2026-05-26",
        name_of_company="Engjell Hasani",
        confidence_score=0.96,
    )
    extract_fn = AsyncMock(return_value=(strong, "gpt-4o", "vision_single"))

    monkeypatch.setattr(settings, "openai_strong_retry_enabled", True)
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_model_strong", "gpt-4o")

    result, model, meta = await service._maybe_retry_strong(
        "test.pdf",
        weak,
        "gpt-4o-mini",
        {"extraction_mode": "vision_single"},
        extract_fn=extract_fn,
    )

    assert model == "gpt-4o"
    assert result.invoice_number == "007"
    assert meta["model_strategy"] == "strong_fallback"
    assert meta["fallback_model_used"] == "gpt-4o"
    assert meta["strong_model_openai_calls"] == 1


def test_targeted_recovery_success_prevents_strong_retry(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_strong_retry_enabled", True)

    result = ExtractionResult(
        invoice_number="INV-1",
        invoice_date="2026-05-01",
        amount=10.0,
        name_of_company="Acme",
        confidence_score=0.5,
    )
    should_retry, reasons = _routing().should_use_strong_fallback(
        result,
        {
            "extraction_mode": "vision_dynamic",
            "targeted_recovery_success": True,
        },
    )
    assert should_retry is False
    assert reasons == []


def test_feature_flag_disables_adaptive_routing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_model_routing_enabled", False)
    monkeypatch.setattr(settings, "openai_strong_retry_enabled", True)
    monkeypatch.setattr(settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_fast_model", "gpt-4o-mini")
    monkeypatch.setattr(settings, "openai_model_strong", "gpt-4o")

    routing = _routing()
    assert routing.fast_model() == "gpt-4o-mini"

    result = ExtractionResult(confidence_score=0.5)
    should_retry, reasons = routing.should_use_strong_fallback(
        result,
        {"extraction_mode": "vision_single"},
    )
    assert should_retry is True
    assert any(reason.startswith("low_confidence") for reason in reasons)
    assert any(reason.startswith("missing_") for reason in reasons)
