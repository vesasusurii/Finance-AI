"""Document preclassification routing tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from config import settings
from core.document_categories import DocumentCategory
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.document_preclassification_service import DocumentPreclassificationService
from services.invoice_extraction_service import InvoiceExtractionService, _ExtractionContext
from services.ocr.pdf_text_extractor import TextLayerHints, parse_text_layer_hints
from services.ocr.pdf_reader import PdfRenderResult


def _service() -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=None,  # type: ignore[arg-type]
        invoice_repo=None,  # type: ignore[arg-type]
        invoice_access_repo=None,  # type: ignore[arg-type]
        audit_repo=None,  # type: ignore[arg-type]
        ai_validation=AIValidationService(),
        openai_client=object(),  # type: ignore[arg-type]
    )


def test_digital_pdf_routes_to_text_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_enabled", True)
    monkeypatch.setattr(settings, "openai_text_first_min_chars", 200)

    hints = parse_text_layer_hints(
        "OpenAI OpCo, LLC\n"
        "Invoice number 3807F638-0011\n"
        "Date of issue February 7, 2026\n"
        "Amount Due (USD) $20.00\n"
        + ("Supporting invoice line detail. " * 40)
    )
    result = DocumentPreclassificationService().classify(
        mime="application/pdf",
        filename="invoice.pdf",
        total_pages=1,
        hints=hints,
        document_category=DocumentCategory.GENERIC,
    )

    assert result.preclassification_type == "digital_pdf"
    assert result.routing_decision == "text_first"
    assert result.use_text_first is True


def test_scanned_pdf_routes_to_vision(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)
    hints = TextLayerHints(raw_text="")

    result = DocumentPreclassificationService().classify(
        mime="application/pdf",
        filename="scan.pdf",
        total_pages=1,
        hints=hints,
        document_category=DocumentCategory.GENERIC,
    )

    assert result.preclassification_type in {"scanned_pdf", "receipt_or_short_invoice"}
    assert result.routing_decision == "vision_full_document"
    assert result.use_text_first is False


def test_long_scanned_pdf_routes_to_vision_dynamic(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)
    hints = TextLayerHints(raw_text="")

    result = DocumentPreclassificationService().classify(
        mime="application/pdf",
        filename="scan-long.pdf",
        total_pages=5,
        hints=hints,
        document_category=DocumentCategory.GENERIC,
    )

    assert result.preclassification_type == "long_invoice"
    assert result.routing_decision == "vision_dynamic"
    assert result.prefer_dynamic_vision is True


def test_image_upload_routes_to_vision_single(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)

    result = DocumentPreclassificationService().classify(
        mime="image/jpeg",
        filename="receipt.jpg",
        total_pages=1,
        hints=TextLayerHints(raw_text=""),
        document_category=DocumentCategory.GENERIC,
    )

    assert result.preclassification_type == "image_upload"
    assert result.routing_decision == "vision_single"


def test_utility_document_gets_utility_prompt_rules(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)

    result = DocumentPreclassificationService().classify(
        mime="application/pdf",
        filename="kesco.pdf",
        total_pages=1,
        hints=parse_text_layer_hints("KESCO electricity invoice NR. REF. 1234567890"),
        document_category=DocumentCategory.UTILITY,
    )

    assert result.preclassification_type == "utility_bill"
    assert result.utility_prompts is True


def test_flag_disabled_keeps_safe_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", False)

    result = DocumentPreclassificationService().classify(
        mime="application/pdf",
        filename="invoice.pdf",
        total_pages=1,
        hints=parse_text_layer_hints("Invoice number 123\nTotal 10.00"),
        document_category=DocumentCategory.GENERIC,
    )

    assert result.routing_decision == "safe_fallback"
    assert result.use_text_first is False


def test_unknown_document_still_classifies_safely(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)

    result = DocumentPreclassificationService().classify(
        mime="application/octet-stream",
        filename="document.bin",
        total_pages=1,
        hints=TextLayerHints(raw_text=""),
        document_category=DocumentCategory.GENERIC,
    )

    assert result.preclassification_type == "unknown"
    assert result.routing_decision == "safe_fallback"


@pytest.mark.asyncio
async def test_scanned_pdf_skips_text_first_in_extraction(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", True)
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_enabled", False)
    monkeypatch.setattr(settings, "openai_adaptive_render_scale", False)
    monkeypatch.setattr(settings, "openai_vision_full_document_max_bytes", 10_000)
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_is_encrypted",
        lambda _content: False,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_page_count",
        lambda _content: 1,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.analyze_pdf_pages",
        lambda _content: [],
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages",
        lambda *_args, **kwargs: PdfRenderResult(
            images=[(b"page", "image/jpeg")],
            page_numbers=[1],
            render_strategy="sequential",
            render_ms=5.0,
            render_parallel_ms=None,
            rendered_page_count=1,
        ),
    )

    full = AsyncMock(
        return_value=(
            ExtractionResult(
                invoice_number="INV-1",
                invoice_date="2026-05-01",
                amount=10.0,
                name_of_company="Acme",
                confidence_score=0.9,
            ),
            "gpt-4o-mini",
            "vision_full_document",
        )
    )
    monkeypatch.setattr(service, "_extract_pdf_pages", full)
    monkeypatch.setattr(service, "_apply_post_vision_pipeline", AsyncMock(side_effect=lambda r, **_k: r))

    _result, _model, meta = await service._extract(
        "scan.pdf",
        "application/pdf",
        b"%PDF",
    )

    full.assert_awaited_once()
    assert meta["preclassification_type"] in {"scanned_pdf", "receipt_or_short_invoice"}
    assert meta["routing_decision"] == "vision_full_document"
