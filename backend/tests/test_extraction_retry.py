from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import InvoiceExtractionService


@pytest.mark.asyncio
async def test_maybe_retry_strong_when_missing_fields():
    weak = ExtractionResult(confidence_score=0.95, needs_review=True)
    strong = ExtractionResult(
        invoice_number="007",
        amount=434.6,
        invoice_date="2026-05-26",
        name_of_company="Engjell Hasani",
        confidence_score=0.96,
    )

    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=MagicMock(),
    )

    extract_fn = AsyncMock(return_value=(strong, "gpt-4o", "vision_single"))

    with patch("services.invoice_extraction_service.settings") as mock_settings:
        mock_settings.openai_strong_retry_enabled = True
        mock_settings.openai_model_strong = "gpt-4o"
        mock_settings.openai_model = "gpt-4o-mini"

        result, model, meta = await service._maybe_retry_strong(
            "test.pdf",
            weak,
            "gpt-4o-mini",
            {},
            extract_fn=extract_fn,
        )

    assert model == "gpt-4o"
    assert result.invoice_number == "007"
    assert "missing_invoice_number" in meta.get("strong_retry_reasons", [])


@pytest.mark.asyncio
async def test_maybe_retry_skipped_when_disabled():
    service = InvoiceExtractionService(
        upload_repo=MagicMock(),
        invoice_repo=MagicMock(),
        invoice_access_repo=MagicMock(),
        audit_repo=MagicMock(),
        ai_validation=AIValidationService(),
        openai_client=MagicMock(),
    )
    weak = ExtractionResult(confidence_score=0.5)
    extract_fn = AsyncMock()

    with patch("services.invoice_extraction_service.settings") as mock_settings:
        mock_settings.openai_strong_retry_enabled = False
        mock_settings.openai_model_strong = "gpt-4o"
        mock_settings.openai_model = "gpt-4o-mini"

        result, model, _ = await service._maybe_retry_strong(
            "test.pdf",
            weak,
            "gpt-4o-mini",
            {},
            extract_fn=extract_fn,
        )

    extract_fn.assert_not_called()
    assert model == "gpt-4o-mini"
    assert result.confidence_score == 0.5
