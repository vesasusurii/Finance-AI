from services.ocr.pdf_text_extractor import parse_text_layer_hints


def test_parse_fatura_invoice_number():
    text = "FATURA - INVOICE 14465\nData e faturës 22.05.2026\nVlera me TVSH 900,00"
    hints = parse_text_layer_hints(text)
    assert hints.invoice_number == "14465"
    assert hints.invoice_date == "22.05.2026"
    assert hints.amount == 900.0


def test_parse_freelancer_invoice_title():
    text = "INVOICE 007\n26.05.2026\nTotal Amount Due: €434,60"
    hints = parse_text_layer_hints(text)
    assert hints.invoice_number == "007"
    assert hints.amount == 434.6


def test_empty_text_returns_empty_hints():
    hints = parse_text_layer_hints("")
    assert not hints.has_usable_text
    assert hints.invoice_number is None


def test_parse_openai_style_invoice_number():
    text = """
    OpenAI OpCo, LLC
    Invoice number 3807F638-0011
    Date of issue February 7, 2026
    Amount Due (USD) $20.00
    """
    hints = parse_text_layer_hints(text)
    assert hints.invoice_number == "3807F638-0011"
