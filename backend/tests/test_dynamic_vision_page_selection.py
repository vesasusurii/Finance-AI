from unittest.mock import AsyncMock

import pytest

from config import settings
from core.document_categories import DocumentCategory
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import InvoiceExtractionService, _ExtractionContext
from services.ocr.pdf_text_extractor import TextLayerHints
from services.ocr.pdf_reader import PdfRenderResult
from services.vision_page_selection_service import score_page, select_vision_pages


def _service() -> InvoiceExtractionService:
    return InvoiceExtractionService(
        upload_repo=None,  # type: ignore[arg-type]
        invoice_repo=None,  # type: ignore[arg-type]
        invoice_access_repo=None,  # type: ignore[arg-type]
        audit_repo=None,  # type: ignore[arg-type]
        ai_validation=AIValidationService(),
        openai_client=object(),  # type: ignore[arg-type]
    )


def _ctx(*, page_texts: tuple[str, ...] = ()) -> _ExtractionContext:
    return _ExtractionContext(
        document_category=DocumentCategory.GENERIC,
        text_hints=TextLayerHints(raw_text=""),
        supplemental_text=None,
        vision_system_prompt="vision",
        batch_system_prompt="batch",
        page_texts=page_texts,
    )


def _mock_render_result(*_args, **kwargs) -> PdfRenderResult:
    indices = kwargs.get("page_indices", [0, 1, 2, 3])
    page_numbers = [index + 1 for index in indices]
    return PdfRenderResult(
        images=[(b"page", "image/jpeg")] * len(page_numbers),
        page_numbers=page_numbers,
        render_strategy="parallel",
        render_ms=10.0,
        render_parallel_ms=8.0,
        rendered_page_count=len(page_numbers),
    )


def test_first_page_always_selected():
    selection = select_vision_pages(total_pages=6, page_texts=[""] * 6)
    assert selection.selected_pages[0] == 1


def test_last_page_selected_for_multipage():
    selection = select_vision_pages(total_pages=6, page_texts=[""] * 6)
    assert selection.selected_pages[-1] == 6


def test_middle_pages_selected_only_when_scored_important():
    page_texts = [
        "Invoice header",
        "Terms and conditions only",
        "Line item description without totals",
        "Grand Total Amount Due 500.00 VAT IBAN DE89370400440532013000",
        "Appendix",
        "Payment footer bank details due date",
    ]
    selection = select_vision_pages(total_pages=6, page_texts=page_texts, max_pages=4)
    assert 1 in selection.selected_pages
    assert 6 in selection.selected_pages
    assert 4 in selection.selected_pages
    assert 2 not in selection.selected_pages
    assert 3 not in selection.selected_pages
    assert len(selection.selected_pages) <= 4


def test_page_scores_include_position_bonuses():
    scores = {
        1: score_page(1, 5, ""),
        2: score_page(2, 5, ""),
        5: score_page(5, 5, ""),
    }
    assert scores[1] > scores[2]
    assert scores[5] > scores[2]


def test_selection_metadata_fields():
    selection = select_vision_pages(total_pages=3, page_texts=["a", "b", "c"])
    meta = selection.metadata()
    assert meta["page_selection_strategy"] == "dynamic_first_last"
    assert meta["selected_vision_pages"] == [1, 3]
    assert meta["skipped_vision_pages"] == [2]
    assert "1" in meta["page_scores"]


@pytest.mark.asyncio
async def test_missing_required_fields_trigger_fallback(monkeypatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_enabled", True)
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_max_pages", 4)
    monkeypatch.setattr(settings, "openai_vision_full_document_max_bytes", 10)
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_is_encrypted",
        lambda _content: False,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_page_count",
        lambda _content: 5,
    )
    monkeypatch.setattr(service, "_build_extraction_context", lambda **_kwargs: _ctx())
    monkeypatch.setattr(service, "_try_text_first_pdf", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "services.invoice_extraction_service.analyze_pdf_pages",
        lambda _content: [],
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages",
        _mock_render_result,
    )

    incomplete = ExtractionResult(
        invoice_number=None,
        invoice_date="2026-05-01",
        amount=10.0,
        name_of_company="Acme",
        confidence_score=0.9,
    )
    complete = ExtractionResult(
        invoice_number="INV-1",
        invoice_date="2026-05-01",
        amount=10.0,
        name_of_company="Acme",
        confidence_score=0.9,
    )

    dynamic_vision = AsyncMock(return_value=incomplete)
    edges = AsyncMock(return_value=(complete, "gpt-4o-mini", "vision_first_last"))
    monkeypatch.setattr(service, "_openai_vision_extract", dynamic_vision)
    monkeypatch.setattr(service, "_extract_pdf_edges_then_middle", edges)
    monkeypatch.setattr(service, "_extract_pdf_pages", AsyncMock())
    monkeypatch.setattr(service, "_apply_post_vision_pipeline", AsyncMock(side_effect=lambda r, **_k: r))

    _result, _model, meta = await service._extract(
        "invoice.pdf",
        "application/pdf",
        b"%PDF",
    )

    dynamic_vision.assert_awaited_once()
    edges.assert_awaited_once()
    assert meta["extraction_mode"] == "vision_dynamic_fallback"
    assert meta["page_selection_strategy"] == "dynamic_first_last"


@pytest.mark.asyncio
async def test_flag_disabled_uses_existing_routing(monkeypatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_enabled", False)
    monkeypatch.setattr(settings, "openai_adaptive_render_scale", False)
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
        "services.invoice_extraction_service.analyze_pdf_pages",
        lambda _content: [],
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages",
        lambda *_args, **kwargs: PdfRenderResult(
            images=[(b"large-page", "image/jpeg")]
            * len(kwargs.get("page_indices", [0, 1, 2, 3])),
            page_numbers=[index + 1 for index in kwargs.get("page_indices", [0, 1, 2, 3])],
            render_strategy="parallel",
            render_ms=20.0,
            render_parallel_ms=15.0,
            rendered_page_count=len(kwargs.get("page_indices", [0, 1, 2, 3])),
        ),
    )

    dynamic = AsyncMock()
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
    monkeypatch.setattr(service, "_extract_pdf_dynamic_selection", dynamic)
    monkeypatch.setattr(service, "_extract_pdf_edges_then_middle", edges)
    monkeypatch.setattr(service, "_extract_pdf_pages", AsyncMock())
    monkeypatch.setattr(service, "_apply_post_vision_pipeline", AsyncMock(side_effect=lambda r, **_k: r))

    _result, _model, meta = await service._extract(
        "invoice.pdf",
        "application/pdf",
        b"%PDF",
    )

    dynamic.assert_not_called()
    edges.assert_awaited_once()
    assert meta["extraction_mode"] == "vision_first_last"
