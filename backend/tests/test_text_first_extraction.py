from services.ocr.pdf_text_extractor import TextLayerHints
from services.ocr.pdf_text_extractor import parse_text_layer_hints
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
    assert result.account_details is None
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


def test_parse_text_layer_hints_common_labels_and_iban():
    text = """
    ADIA Group SH.P.K.
    Invoice No: INV-26063
    Invoice date: 15.05.2026
    Grand Total EUR 220.66
    IBAN XK051701010500018287
    """

    hints = parse_text_layer_hints(text)

    assert hints.invoice_number == "INV-26063"
    assert hints.invoice_date == "15.05.2026"
    assert hints.amount == 220.66
    assert hints.name_of_company == "ADIA Group SH.P.K."
    assert hints.account_details == "XK051701010500018287"
