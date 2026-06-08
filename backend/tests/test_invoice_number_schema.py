from schemas.invoice import ExtractionResult, InvoiceUpdate


def test_extraction_result_keeps_display_invoice_number():
    result = ExtractionResult.model_validate({"invoice_number": "1/2026/0048"})
    assert result.invoice_number == "1/2026/0048"


def test_invoice_update_trims_only():
    update = InvoiceUpdate.model_validate({"invoice_number": "  ABC-2024-001  "})
    assert update.invoice_number == "ABC-2024-001"
