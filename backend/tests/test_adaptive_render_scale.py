"""Adaptive PDF render scale selection and selective rendering."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from config import settings
from core.document_categories import DocumentCategory
from schemas.invoice import ExtractionResult
from services.adaptive_render_scale_service import build_adaptive_render_plan, choose_render_tier
from services.ai_validation_service import AIValidationService
from services.invoice_extraction_service import InvoiceExtractionService, _ExtractionContext
from services.ocr.pdf_page_analyzer import PageContentAnalysis
from services.ocr.pdf_text_extractor import TextLayerHints
from services.ocr.pdf_reader import PdfRenderResult


def _analysis(
    page_num: int,
    *,
    text_length: int = 500,
    mostly_whitespace: bool = False,
    mostly_line_items: bool = False,
    has_totals: bool = False,
    has_invoice_number: bool = False,
    avg_font_size: float | None = 11.0,
    text_block_count: int = 8,
    text_density: float = 0.2,
) -> PageContentAnalysis:
    return PageContentAnalysis(
        page_num=page_num,
        text_length=text_length,
        text_density=text_density,
        whitespace_ratio=0.95 if mostly_whitespace else 0.2,
        avg_font_size=avg_font_size,
        text_block_count=text_block_count,
        has_totals=has_totals,
        has_invoice_number=has_invoice_number,
        has_vat=False,
        has_bank_details=False,
        has_signature=False,
        mostly_line_items=mostly_line_items,
        mostly_whitespace=mostly_whitespace,
    )


def _render_result(
    *,
    page_numbers: list[int],
    images: list[tuple[bytes, str]] | None = None,
) -> PdfRenderResult:
    imgs = images or [(b"page", "image/jpeg") for _ in page_numbers]
    return PdfRenderResult(
        images=imgs,
        page_numbers=page_numbers,
        render_strategy="parallel",
        render_ms=10.0,
        render_parallel_ms=8.0,
        rendered_page_count=len(page_numbers),
        render_scale_strategy="adaptive",
        actual_image_bytes=sum(len(img) for img, _ in imgs),
    )


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


def test_first_page_always_renders_high():
    tier, reason = choose_render_tier(
        page_num=1,
        total_pages=4,
        analysis=_analysis(1),
    )
    assert tier == "high"
    assert "header" in reason


def test_last_page_renders_high():
    tier, _reason = choose_render_tier(
        page_num=4,
        total_pages=4,
        analysis=_analysis(4, mostly_line_items=True),
    )
    assert tier == "high"


def test_dense_page_renders_high():
    tier, reason = choose_render_tier(
        page_num=2,
        total_pages=4,
        analysis=_analysis(
            2,
            text_block_count=25,
            text_density=0.5,
            avg_font_size=7.0,
        ),
    )
    assert tier == "high"
    assert reason in {"small text", "dense table"}


def test_sparse_page_renders_low():
    tier, reason = choose_render_tier(
        page_num=2,
        total_pages=4,
        analysis=_analysis(2, mostly_whitespace=True, text_length=10),
    )
    assert tier == "low"
    assert "whitespace" in reason


def test_line_items_with_large_font_renders_low():
    tier, reason = choose_render_tier(
        page_num=2,
        total_pages=4,
        analysis=_analysis(
            2,
            mostly_line_items=True,
            avg_font_size=12.0,
            has_totals=False,
        ),
    )
    assert tier == "low"
    assert "line items" in reason


def test_feature_flag_disabled_uses_fixed_scale(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_adaptive_render_scale", False)
    monkeypatch.setattr(settings, "openai_pdf_render_scale", 1.5)
    plan = build_adaptive_render_plan(
        total_pages=3,
        pages_to_render=[1, 2, 3],
        analyses=[_analysis(i) for i in (1, 2, 3)],
    )
    assert plan.strategy == "fixed"
    assert all(item.scale == 1.5 for item in plan.pages)


def test_build_plan_skips_unrendered_pages():
    plan = build_adaptive_render_plan(
        total_pages=4,
        pages_to_render=[1, 4],
        analyses=[_analysis(i) for i in (1, 2, 3, 4)],
    )
    assert plan.skipped_pages == (2, 3)
    assert {item.page_num for item in plan.pages} == {1, 4}


@pytest.mark.asyncio
async def test_dynamic_page_selection_still_works(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_enabled", True)
    monkeypatch.setattr(settings, "openai_adaptive_render_scale", True)
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_is_encrypted",
        lambda _content: False,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.pdf_page_count",
        lambda _content: 4,
    )
    monkeypatch.setattr(
        "services.invoice_extraction_service.analyze_pdf_pages",
        lambda _content: [_analysis(i) for i in (1, 2, 3, 4)],
    )
    monkeypatch.setattr(service, "_build_extraction_context", lambda **_kwargs: _ctx())
    monkeypatch.setattr(service, "_try_text_first_pdf", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages",
        lambda *_args, **kwargs: _render_result(
            page_numbers=[index + 1 for index in kwargs.get("page_indices", [0, 3])],
        ),
    )

    complete = ExtractionResult(
        invoice_number="INV-1",
        invoice_date="2026-05-01",
        amount=10.0,
        name_of_company="Acme",
        confidence_score=0.9,
    )
    vision = AsyncMock(return_value=complete)
    monkeypatch.setattr(service, "_openai_vision_extract", vision)
    monkeypatch.setattr(service, "_apply_post_vision_pipeline", AsyncMock(side_effect=lambda r, **_k: r))

    _result, _model, meta = await service._extract(
        "invoice.pdf",
        "application/pdf",
        b"%PDF",
    )

    assert meta["extraction_mode"] == "vision_dynamic"
    assert meta["page_selection_strategy"] == "dynamic_first_last"
    assert meta["render_scale_strategy"] == "adaptive"
    vision.assert_awaited_once()
    assert vision.await_args.kwargs["page_numbers"] == [1, 4]


@pytest.mark.asyncio
async def test_flag_disabled_restores_fixed_render_scale(monkeypatch: pytest.MonkeyPatch):
    service = _service()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_dynamic_page_selection_enabled", False)
    monkeypatch.setattr(settings, "openai_adaptive_render_scale", False)
    monkeypatch.setattr(settings, "openai_preclassification_routing_enabled", False)
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

    captured: dict = {}

    def capture_render(*_args, **kwargs):
        captured.update(kwargs)
        return _render_result(page_numbers=[1, 2, 3, 4])

    monkeypatch.setattr(
        "services.invoice_extraction_service.render_pdf_pages",
        capture_render,
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

    await service._extract("invoice.pdf", "application/pdf", b"%PDF")

    assert captured.get("render_scale_strategy") == "fixed"
    assert captured.get("page_indices") == [0, 1, 2, 3]
