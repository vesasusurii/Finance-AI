"""Targeted missing-field recovery tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from config import settings
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.targeted_field_recovery_service import TargetedFieldRecoveryService


def _service(client: object | None = object()) -> TargetedFieldRecoveryService:
    return TargetedFieldRecoveryService(
        openai_client=client,  # type: ignore[arg-type]
        ai_validation=AIValidationService(),
    )


def _complete_result() -> ExtractionResult:
    return ExtractionResult(
        invoice_number="INV-1",
        invoice_date="2026-05-01",
        amount=100.0,
        name_of_company="Acme",
        currency="EUR",
        confidence_score=0.9,
    )


def _missing_invoice_number() -> ExtractionResult:
    return ExtractionResult(
        invoice_number=None,
        invoice_date="2026-05-01",
        amount=100.0,
        name_of_company="Acme",
        confidence_score=0.85,
    )


def test_no_recovery_when_extraction_is_complete():
    service = _service()
    should_run, fields = service.should_attempt(
        _complete_result(),
        images=[(b"page", "image/jpeg")],
    )
    assert should_run is False
    assert fields == []


def test_no_recovery_when_more_than_max_fields_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_enabled", True)
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_max_fields", 2)

    result = ExtractionResult(
        invoice_number=None,
        invoice_date=None,
        amount=None,
        name_of_company="Acme",
        confidence_score=0.9,
    )
    service = _service()
    should_run, fields = service.should_attempt(
        result,
        images=[(b"page", "image/jpeg")],
    )
    assert should_run is False
    assert fields == []


def test_recovery_runs_when_one_critical_field_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_enabled", True)
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_max_fields", 2)
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_min_confidence", 0.65)

    service = _service()
    should_run, fields = service.should_attempt(
        _missing_invoice_number(),
        images=[(b"page", "image/jpeg")],
    )
    assert should_run is True
    assert fields == ["invoice_number"]


def test_flag_disabled_skips_targeted_recovery(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_enabled", False)

    service = _service()
    should_run, _fields = service.should_attempt(
        _missing_invoice_number(),
        images=[(b"page", "image/jpeg")],
    )
    assert should_run is False


@pytest.mark.asyncio
async def test_recovery_result_merges_into_final_extraction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_enabled", True)
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_max_fields", 2)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"invoice_number": "INV-99"}'))
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    service = _service(mock_client)
    outcome = await service.recover_missing_fields(
        _missing_invoice_number(),
        images=[(b"page", "image/jpeg")],
        model="gpt-4o-mini",
        filename="invoice.pdf",
    )

    assert outcome.metadata["targeted_recovery_used"] is True
    assert outcome.metadata["targeted_recovery_success"] is True
    assert outcome.metadata["targeted_recovery_openai_calls"] == 1
    assert outcome.result.invoice_number == "INV-99"
    mock_client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_recovery_does_not_break_extraction(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_enabled", True)
    monkeypatch.setattr(settings, "openai_targeted_field_recovery_max_fields", 2)

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    service = _service(mock_client)
    original = _missing_invoice_number()
    outcome = await service.recover_missing_fields(
        original,
        images=[(b"page", "image/jpeg")],
        model="gpt-4o-mini",
        filename="invoice.pdf",
    )

    assert outcome.metadata["targeted_recovery_used"] is True
    assert outcome.metadata["targeted_recovery_success"] is False
    assert outcome.result.invoice_number is None
    assert outcome.result.needs_review is True
    assert "targeted_recovery_failed" in outcome.result.review_reasons


def test_select_images_uses_first_and_last_for_mixed_fields():
    service = _service()
    images = [(b"first", "image/jpeg"), (b"middle", "image/jpeg"), (b"last", "image/jpeg")]
    selected = service._select_images(["invoice_number", "amount"], images)
    assert selected == [images[0], images[-1]]
