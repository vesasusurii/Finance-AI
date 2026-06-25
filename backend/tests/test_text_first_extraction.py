from services.ocr.pdf_text_extractor import TextLayerHints
from services.text_first_extraction_service import TextFirstExtractionService


def test_can_attempt_requires_enough_text():
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(raw_text="short")
    assert not svc.can_attempt(total_pages=1, hints=hints)


def test_result_from_hints_when_all_critical_present():
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-26063",
        invoice_date="15.05.2026",
        amount=220.66,
        name_of_company="ADIA Group SH.P.K.",
    )
    result = svc.result_from_hints(hints)
    assert result is not None
    assert result.invoice_number == "INV-26063"
    assert result.amount == 220.66
    assert result.confidence_score >= 0.85


def test_result_from_hints_returns_none_when_incomplete():
    svc = TextFirstExtractionService(openai_client=None)
    hints = TextLayerHints(
        raw_text="x" * 300,
        invoice_number="INV-1",
        invoice_date=None,
        amount=10.0,
        name_of_company="Acme",
    )
    assert svc.result_from_hints(hints) is None
