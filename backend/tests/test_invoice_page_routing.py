from unittest.mock import AsyncMock

import pytest

from config import settings
from core.document_categories import DocumentCategory
from schemas.invoice import ExtractionResult
from services.invoice_extraction_service import InvoiceExtractionService, _ExtractionContext
from services.ocr.pdf_text_extractor import TextLayerHints
from services.ai_validation_service import AIValidationService


def _service() -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=None,  # type: ignore[arg-type]
        invoice_repo=None,  # type: ignore[arg-type]
        invoice_access_repo=None,  # type: ignore[arg-type]
        audit_repo=None,  # type: ignore[arg-type]
        ai_validation=AIValidationService(),
        openai_client=object(),  # type: ignore[arg-type]
    )


def _ctx() -> _ExtractionContext:
    return _ExtractionContext(
        document_category=DocumentCategory.GENERIC,
        text_hints=TextLayerHints(raw_text=""),
        supplemental_text=None,
        vision_system_prompt="vision",
        batch_system_prompt="batch",
    )


@pytest.mark.asyncio
async def test_four_small_pdf_pages_use_single_full_document_call(monkeypatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_vision_full_document_max_bytes", 10_000)
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_is_encrypted",
        lambda _content: False,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_page_count",
        lambda _content: 4,
    )
    monkeypatch.setattr(service, "_build_extraction_context", lambda **_kwargs: _ctx())
    monkeypatch.setattr(service, "_try_text_first_pdf", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages_as_images",
        lambda *_args, **_kwargs: [(b"small", "image/jpeg")] * 4,
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
    edges = AsyncMock()
    monkeypatch.setattr(service, "_extract_pdf_pages", full)
    monkeypatch.setattr(service, "_extract_pdf_edges_then_middle", edges)

    _result, _model, meta = await service._extract(
        "invoice.pdf",
        "application/pdf",
        b"%PDF",
    )

    full.assert_awaited_once()
    edges.assert_not_called()
    assert meta["extraction_mode"] == "vision_full_document"
    assert meta["pages_processed"] == 4


@pytest.mark.asyncio
async def test_four_large_pdf_pages_use_first_last_gate(monkeypatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_vision_full_document_max_bytes", 10)
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_is_encrypted",
        lambda _content: False,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_page_count",
        lambda _content: 4,
    )
    monkeypatch.setattr(service, "_build_extraction_context", lambda **_kwargs: _ctx())
    monkeypatch.setattr(service, "_try_text_first_pdf", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages_as_images",
        lambda *_args, **_kwargs: [(b"large-page", "image/jpeg")] * 4,
    )

    full = AsyncMock()
    edges = AsyncMock(
        return_value=(
            ExtractionResult(
                invoice_number="INV-1",
                invoice_date="2026-05-01",
                amount=10.0,
                name_of_company="Acme",
                confidence_score=0.9,
            ),
            "gpt-4o-mini",
            "vision_first_last",
        )
    )
    monkeypatch.setattr(service, "_extract_pdf_pages", full)
    monkeypatch.setattr(service, "_extract_pdf_edges_then_middle", edges)

    _result, _model, meta = await service._extract(
        "invoice.pdf",
        "application/pdf",
        b"%PDF",
    )

    edges.assert_awaited_once()
    full.assert_not_called()
    assert meta["extraction_mode"] == "vision_first_last"
    assert meta["pages_processed"] == 2
