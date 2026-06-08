from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.hybrid_extraction_service import HybridExtractionService
from services.ocr.pdf_text_extractor import TextLayerHints


def test_hybrid_fills_missing_invoice_number():
    vision = ExtractionResult(
        amount=900.0,
        invoice_date="2026-05-22",
        name_of_company="Sarajeva Steak House SH.P.K.",
        confidence_score=0.8,
    )
    hints = TextLayerHints(raw_text="x" * 100, invoice_number="14465")
    merged = HybridExtractionService(AIValidationService()).merge(vision, hints)
    assert merged.invoice_number == "14465"
    assert merged.amount == 900.0


def test_hybrid_does_not_override_vision_invoice_number():
    vision = ExtractionResult(
        invoice_number="99999",
        amount=100.0,
        confidence_score=0.9,
    )
    hints = TextLayerHints(raw_text="x" * 100, invoice_number="14465")
    merged = HybridExtractionService(AIValidationService()).merge(vision, hints)
    assert merged.invoice_number == "99999"
